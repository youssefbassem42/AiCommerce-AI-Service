import time
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from openai import AsyncOpenAI
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
from app.utils.token_utils import calculate_cost, calculate_tokens

logger = logging.getLogger("ai_service")

class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI Provider implementation handling Chat, Streaming, Embeddings,
    Structured Outputs, Tool Calling, and Vision for OpenAI models.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or KeyManager().get_provider_api_key("openai") or "mock-key"
        # Async OpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=ai_settings.REQUEST_TIMEOUT,
        )

    def _map_messages(self, messages: List[MessageDTO]) -> List[Dict[str, Any]]:
        mapped = []
        for msg in messages:
            msg_dict: Dict[str, Any] = {"role": msg.role}
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            
            if isinstance(msg.content, list):
                content_list = []
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        content_list.append({
                            "type": "image_url",
                            "image_url": {
                                "url": item["image_url"]["url"],
                                "detail": item["image_url"].get("detail", "auto"),
                            }
                        })
                    else:
                        content_list.append(item)
                msg_dict["content"] = content_list
            else:
                msg_dict["content"] = msg.content

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

            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            response = await self.client.chat.completions.create(
                **kwargs, timeout=actual_timeout
            )
            latency = (time.perf_counter() - start_time) * 1000

            choice = response.choices[0]
            
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    ToolCallDTO(
                        id=tc.id,
                        type=tc.type,
                        function_name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in choice.message.tool_calls
                ]

            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            total_tokens = response.usage.total_tokens if response.usage else (prompt_tokens + completion_tokens)
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

            return ChatResponse(
                id=response.id,
                model=response.model,
                provider="openai",
                message=MessageDTO(
                    role=choice.message.role,
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

        return await execute_with_retry("openai", _run, max_retries=ai_settings.MAX_RETRIES)

    async def stream(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "messages": self._map_messages(request.messages),
            "stream": True,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
        
        try:
            response_stream = await self.client.chat.completions.create(
                **kwargs, timeout=actual_timeout
            )
            async for chunk in response_stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                content = choice.delta.content or ""
                finish_reason = choice.finish_reason if hasattr(choice, "finish_reason") else None
                
                # Check for usage in chunk (some models output usage in final chunk)
                usage = None
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = UsageDTO(
                        prompt_tokens=chunk.usage.prompt_tokens,
                        completion_tokens=chunk.usage.completion_tokens,
                        total_tokens=chunk.usage.total_tokens,
                        cost=calculate_cost(chunk.usage.prompt_tokens, chunk.usage.completion_tokens, request.model)
                    )

                yield StreamingChunkDTO(
                    id=chunk.id,
                    model=chunk.model,
                    provider="openai",
                    content=content,
                    finish_reason=finish_reason,
                    usage=usage,
                )
        except Exception as e:
            raise map_provider_exception("openai", e)

    async def embeddings(
        self, request: EmbeddingRequest, timeout: Optional[float] = None
    ) -> EmbeddingResponse:
        async def _run():
            kwargs: Dict[str, Any] = {
                "model": request.model,
                "input": request.input,
            }
            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            response = await self.client.embeddings.create(**kwargs, timeout=actual_timeout)

            embeddings = [data.embedding for data in response.data]
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            cost = calculate_cost(prompt_tokens, 0, request.model)

            return EmbeddingResponse(
                model=response.model,
                provider="openai",
                embeddings=embeddings,
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    total_tokens=prompt_tokens,
                    cost=cost,
                ),
            )

        return await execute_with_retry("openai", _run, max_retries=ai_settings.MAX_RETRIES)

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            # Call models.list as a low-cost query
            await self.client.models.list(timeout=5.0)
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="healthy",
                provider="openai",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="unhealthy",
                provider="openai",
                latency_ms=latency,
                details=str(e),
            )

    async def list_models(self) -> List[str]:
        from app.core.model_registry import ModelRegistry
        return [m.name for m in ModelRegistry.list_models_by_provider("openai")]

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: Optional[float] = None
    ) -> ChatResponse:
        """
        Generate structured output adhering to a specific JSON schema/Pydantic model.
        Uses OpenAI's beta.chat.completions.parse where available.
        """
        async def _run():
            start_time = time.perf_counter()
            kwargs: Dict[str, Any] = {
                "model": request.model,
                "messages": self._map_messages(request.messages),
                "response_format": response_schema,
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.top_p is not None:
                kwargs["top_p"] = request.top_p
            if request.max_tokens is not None:
                kwargs["max_tokens"] = request.max_tokens

            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            response = await self.client.beta.chat.completions.parse(
                **kwargs, timeout=actual_timeout
            )
            latency = (time.perf_counter() - start_time) * 1000

            choice = response.choices[0]
            parsed_content = choice.message.content or ""

            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            total_tokens = response.usage.total_tokens if response.usage else (prompt_tokens + completion_tokens)
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

            return ChatResponse(
                id=response.id,
                model=response.model,
                provider="openai",
                message=MessageDTO(
                    role=choice.message.role,
                    content=parsed_content,
                ),
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                ),
                latency_ms=latency,
            )

        return await execute_with_retry("openai", _run, max_retries=ai_settings.MAX_RETRIES)

    async def tool_call(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> ChatResponse:
        # tool calling is natively supported via standard chat method when tools are passed
        return await self.chat(request, timeout)
