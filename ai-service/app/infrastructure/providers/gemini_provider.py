import time
import json
import base64
import logging
import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional
from google import genai
from google.genai import types
from app.infrastructure.providers.base import BaseLLMProvider
from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    MessageDTO,
    StreamingChunkDTO,
    UsageDTO,
    ToolCallDTO,
)
from app.core.ai_settings import ai_settings
from app.infrastructure.security.key_manager import KeyManager
from app.utils.ai_error_handler import map_provider_exception, execute_with_retry
from app.utils.token_utils import calculate_cost

logger = logging.getLogger("ai_service")


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Provider using the new google.genai SDK.
    Supports Chat, Streaming, Embeddings, Tool Calling, Vision, and Structured Outputs.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or KeyManager().get_provider_api_key("gemini") or "mock-key"
        self.client = genai.Client(api_key=self.api_key)

    async def _download_image_bytes(self, url: str) -> tuple[bytes, str]:
        if url.startswith("data:"):
            header, encoded = url.split(";base64,")
            media_type = header.replace("data:", "")
            return base64.b64decode(encoded), media_type

        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url, timeout=10.0)
            response.raise_for_status()
            media_type = response.headers.get("content-type", "image/jpeg")
            return response.content, media_type

    def _build_contents(
        self, messages: List[MessageDTO]
    ) -> tuple[Optional[str], List[types.Content]]:
        system_instruction = None
        contents: List[types.Content] = []

        for msg in messages:
            if msg.role in ("system", "developer"):
                system_instruction = msg.content if isinstance(msg.content, str) else str(msg.content)
                continue

            parts: List[types.Part] = []

            if msg.role == "tool":
                parts.append(
                    types.Part.from_function_response(
                        name=msg.name or "tool_call",
                        response={"result": msg.content},
                    )
                )
            elif isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict):
                        if item.get("type") == "image_url":
                            parts.append(
                                types.Part.from_text(
                                    text=f"[Image: {item['image_url']['url']}]"
                                )
                            )
                        elif item.get("type") == "text":
                            parts.append(types.Part.from_text(text=item["text"]))
                    else:
                        parts.append(types.Part.from_text(text=str(item)))
            else:
                parts.append(types.Part.from_text(text=msg.content))

            # Map assistant tool calls as function_call parts
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.arguments)
                    except Exception:
                        args = {"args": tc.arguments}
                    parts.append(
                        types.Part.from_function_call(
                            name=tc.function_name,
                            args=args,
                        )
                    )

            role = "user" if msg.role in ("user", "tool") else "model"
            contents.append(types.Content(role=role, parts=parts))

        return system_instruction, contents

    def _build_tools(self, request: ChatRequest) -> Optional[List[types.Tool]]:
        if not request.tools:
            return None
        declarations = []
        for tool in request.tools:
            declarations.append(
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters,
                )
            )
        return [types.Tool(function_declarations=declarations)]

    def _build_config(self, request: ChatRequest) -> types.GenerateContentConfig:
        config_kwargs: Dict[str, Any] = {}
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            config_kwargs["top_p"] = request.top_p
        if request.max_tokens is not None:
            config_kwargs["max_output_tokens"] = request.max_tokens
        if request.json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        tools = self._build_tools(request)
        if tools:
            config_kwargs["tools"] = tools

        return types.GenerateContentConfig(**config_kwargs)

    def _parse_response(
        self, response: Any, request: ChatRequest, start_time: float
    ) -> ChatResponse:
        latency = (time.perf_counter() - start_time) * 1000
        text_content = ""
        tool_calls: List[ToolCallDTO] = []

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.text:
                    text_content += part.text
                elif part.function_call:
                    tool_calls.append(
                        ToolCallDTO(
                            id=part.function_call.name,
                            type="function",
                            function_name=part.function_call.name,
                            arguments=json.dumps(dict(part.function_call.args))
                            if part.function_call.args
                            else "{}",
                        )
                    )

        usage_meta = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage_meta, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage_meta, "candidates_token_count", 0) or 0
        total_tokens = getattr(usage_meta, "total_token_count", 0) or (
            prompt_tokens + completion_tokens
        )
        cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

        return ChatResponse(
            id=f"gemini-{int(time.time())}",
            model=request.model,
            provider="gemini",
            message=MessageDTO(
                role="assistant",
                content=text_content,
                tool_calls=tool_calls if tool_calls else None,
            ),
            usage=UsageDTO(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost=cost,
            ),
            latency_ms=latency,
        )

    async def chat(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> ChatResponse:
        async def _run():
            start_time = time.perf_counter()
            system_instruction, contents = self._build_contents(request.messages)

            config = self._build_config(request)
            if system_instruction:
                config.system_instruction = system_instruction

            response = await self.client.aio.models.generate_content(
                model=request.model,
                contents=contents,
                config=config,
            )
            return self._parse_response(response, request, start_time)

        return await execute_with_retry(
            "gemini", _run, max_retries=ai_settings.MAX_RETRIES
        )

    async def stream(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        system_instruction, contents = self._build_contents(request.messages)
        config = self._build_config(request)
        if system_instruction:
            config.system_instruction = system_instruction

        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=request.model,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                content = ""
                if chunk.candidates and chunk.candidates[0].content:
                    for part in chunk.candidates[0].content.parts:
                        if part.text:
                            content += part.text

                usage = None
                usage_meta = getattr(chunk, "usage_metadata", None)
                if usage_meta:
                    pt = getattr(usage_meta, "prompt_token_count", 0) or 0
                    ct = getattr(usage_meta, "candidates_token_count", 0) or 0
                    tt = getattr(usage_meta, "total_token_count", 0) or (pt + ct)
                    usage = UsageDTO(
                        prompt_tokens=pt,
                        completion_tokens=ct,
                        total_tokens=tt,
                        cost=calculate_cost(pt, ct, request.model),
                    )

                yield StreamingChunkDTO(
                    id=f"gemini-chunk-{int(time.time())}",
                    model=request.model,
                    provider="gemini",
                    content=content,
                    finish_reason=None,
                    usage=usage,
                )
        except Exception as e:
            raise map_provider_exception("gemini", e)

    async def embeddings(
        self, request: EmbeddingRequest, timeout: Optional[float] = None
    ) -> EmbeddingResponse:
        async def _run():
            config = types.EmbedContentConfig(output_dimensionality=768)
            response = await self.client.aio.models.embed_content(
                model=request.model,
                contents=request.input,
                config=config,
            )

            embeddings_list = []
            if hasattr(response, "embeddings") and response.embeddings:
                for emb in response.embeddings:
                    embeddings_list.append(list(emb.values))
            elif hasattr(response, "embedding"):
                embeddings_list.append(list(response.embedding.values))

            input_list = (
                [request.input] if isinstance(request.input, str) else request.input
            )
            prompt_tokens = sum(len(text) // 4 for text in input_list)
            cost = calculate_cost(prompt_tokens, 0, request.model)

            return EmbeddingResponse(
                model=request.model,
                provider="gemini",
                embeddings=embeddings_list,
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    total_tokens=prompt_tokens,
                    cost=cost,
                ),
            )

        return await execute_with_retry(
            "gemini", _run, max_retries=ai_settings.MAX_RETRIES
        )

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            await self.client.aio.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents="Ping",
                config=types.GenerateContentConfig(max_output_tokens=1),
            )
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(status="healthy", provider="gemini", latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="unhealthy",
                provider="gemini",
                latency_ms=latency,
                details=str(e),
            )

    async def list_models(self) -> List[str]:
        from app.core.model_registry import ModelRegistry

        return [m.name for m in ModelRegistry.list_models_by_provider("gemini")]

    async def structured_output(
        self,
        request: ChatRequest,
        response_schema: Any,
        timeout: Optional[float] = None,
    ) -> ChatResponse:
        async def _run():
            start_time = time.perf_counter()
            system_instruction, contents = self._build_contents(request.messages)

            config_kwargs: Dict[str, Any] = {
                "response_mime_type": "application/json",
            }
            # If it's a Pydantic model, extract JSON schema
            if hasattr(response_schema, "model_json_schema"):
                config_kwargs["response_schema"] = response_schema.model_json_schema()
            elif isinstance(response_schema, dict):
                config_kwargs["response_schema"] = response_schema
            else:
                config_kwargs["response_schema"] = response_schema

            if request.temperature is not None:
                config_kwargs["temperature"] = request.temperature
            if request.top_p is not None:
                config_kwargs["top_p"] = request.top_p
            if request.max_tokens is not None:
                config_kwargs["max_output_tokens"] = request.max_tokens

            config = types.GenerateContentConfig(**config_kwargs)
            if system_instruction:
                config.system_instruction = system_instruction

            response = await self.client.aio.models.generate_content(
                model=request.model,
                contents=contents,
                config=config,
            )
            return self._parse_response(response, request, start_time)

        return await execute_with_retry(
            "gemini", _run, max_retries=ai_settings.MAX_RETRIES
        )

    async def tool_call(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> ChatResponse:
        return await self.chat(request, timeout)
