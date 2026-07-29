import time
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from mistralai.client.sdk import Mistral
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

class MistralProvider(BaseLLMProvider):
    """
    Mistral Provider implementation.
    Handles Chat, Streaming, Embeddings, Tool Calling, and Structured Outputs.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or KeyManager().get_provider_api_key("mistral") or ""
        # Mistral uses client wrapper
        self.client = Mistral(
            api_key=self.api_key,
        )

    def _map_messages(self, messages: List[MessageDTO]) -> List[Dict[str, Any]]:
        mapped = []
        for msg in messages:
            msg_dict: Dict[str, Any] = {"role": msg.role}
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            
            # Map content
            if isinstance(msg.content, list):
                text_parts = []
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item["text"])
                    elif isinstance(item, dict) and item.get("type") == "image_url":
                        # Mistral Large supports image URLs in multimodal contexts
                        text_parts.append(f"[Image URL: {item['image_url']['url']}]")
                    else:
                        text_parts.append(str(item))
                msg_dict["content"] = " ".join(text_parts)
            else:
                msg_dict["content"] = msg.content

            # Map assistant tool calls
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            mapped.append(msg_dict)
        return mapped

    def _map_tools(self, request: ChatRequest) -> Optional[List[Dict[str, Any]]]:
        if not request.tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in request.tools
        ]

    async def chat(self, request: ChatRequest, timeout: Optional[float] = None) -> ChatResponse:
        async def _run():
            start_time = time.perf_counter()
            kwargs: Dict[str, Any] = {
                "model": request.model,
                "messages": self._map_messages(request.messages),
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.top_p is not None:
                kwargs["top_p"] = request.top_p
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens
            if request.json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            tools = self._map_tools(request)
            if tools:
                kwargs["tools"] = tools
                if request.tool_choice:
                    kwargs["tool_choice"] = request.tool_choice

            # Run mistral chat
            response = await self.client.chat.complete_async(**kwargs)
            latency = (time.perf_counter() - start_time) * 1000

            choice = response.choices[0]
            
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    ToolCallDTO(
                        id=tc.id or f"mistral-tc-{idx}",
                        type="function",
                        function_name=tc.function.name,
                        arguments=tc.function.arguments if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments),
                    )
                    for idx, tc in enumerate(choice.message.tool_calls)
                ]

            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            total_tokens = response.usage.total_tokens if response.usage else (prompt_tokens + completion_tokens)
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

            return ChatResponse(
                id=response.id,
                model=response.model,
                provider="mistral",
                message=MessageDTO(
                    role=choice.message.role or "assistant",
                    content=choice.message.content or "",
                    tool_calls=tool_calls,
                ),
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                ),
                latency_ms=latency,
            )

        return await execute_with_retry("mistral", _run, max_retries=ai_settings.MAX_RETRIES)

    async def stream(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "messages": self._map_messages(request.messages),
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response_stream = await self.client.chat.stream_async(**kwargs)
            async for chunk in response_stream:
                if not chunk.data.choices:
                    continue
                choice = chunk.data.choices[0]
                content = choice.delta.content or ""
                finish_reason = choice.finish_reason if hasattr(choice, "finish_reason") else None
                
                usage = None
                if hasattr(chunk.data, "usage") and chunk.data.usage:
                    usage = UsageDTO(
                        prompt_tokens=chunk.data.usage.prompt_tokens,
                        completion_tokens=chunk.data.usage.completion_tokens,
                        total_tokens=chunk.data.usage.total_tokens,
                        cost=calculate_cost(chunk.data.usage.prompt_tokens, chunk.data.usage.completion_tokens, request.model)
                    )

                yield StreamingChunkDTO(
                    id=chunk.data.id,
                    model=chunk.data.model,
                    provider="mistral",
                    content=content,
                    finish_reason=finish_reason,
                    usage=usage,
                )
        except Exception as e:
            raise map_provider_exception("mistral", e)

    async def embeddings(
        self, request: EmbeddingRequest, timeout: Optional[float] = None
    ) -> EmbeddingResponse:
        async def _run():
            inputs = request.input if isinstance(request.input, list) else [request.input]
            
            response = await self.client.embeddings.create_async(
                model=request.model,
                inputs=inputs,
            )

            embeddings = [data.embedding for data in response.data]
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            cost = calculate_cost(prompt_tokens, 0, request.model)

            return EmbeddingResponse(
                model=response.model,
                provider="mistral",
                embeddings=embeddings,
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    total_tokens=prompt_tokens,
                    cost=cost,
                ),
            )

        return await execute_with_retry("mistral", _run, max_retries=ai_settings.MAX_RETRIES)

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            # Low cost health call: request list of models
            await self.client.models.list_async()
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="healthy",
                provider="mistral",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="unhealthy",
                provider="mistral",
                latency_ms=latency,
                details=str(e),
            )

    async def list_models(self) -> List[str]:
        from app.core.model_registry import ModelRegistry
        return [m.name for m in ModelRegistry.list_models_by_provider("mistral")]

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: Optional[float] = None
    ) -> ChatResponse:
        """
        Generate structured output. For Mistral, we set response_format={"type": "json_object"}
        and inject schema details in the messages.
        """
        import json
        if hasattr(response_schema, "model_json_schema"):
            schema_desc = json.dumps(response_schema.model_json_schema())
        elif hasattr(response_schema, "schema"):
            schema_desc = json.dumps(response_schema.schema())
        else:
            schema_desc = str(response_schema)

        request_copy = ChatRequest(**request.model_dump())
        request_copy.json_mode = True
        
        instruction = f"\nReturn a JSON object matching this schema:\n{schema_desc}"
        if request_copy.messages:
            last_msg = request_copy.messages[-1]
            if isinstance(last_msg.content, str):
                last_msg.content += instruction
            else:
                last_msg.content.append({"type": "text", "text": instruction})
        
        return await self.chat(request_copy, timeout)

    async def tool_call(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> ChatResponse:
        return await self.chat(request, timeout)
