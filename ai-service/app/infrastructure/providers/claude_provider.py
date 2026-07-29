import time
import logging
import base64
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import httpx
from anthropic import AsyncAnthropic
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

class ClaudeProvider(BaseLLMProvider):
    """
    Anthropic Claude Provider implementation.
    Handles Chat, Streaming, Vision, Tool Calling, and Structured Outputs.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or KeyManager().get_provider_api_key("claude") or ""
        self.client = AsyncAnthropic(
            api_key=self.api_key,
            timeout=ai_settings.REQUEST_TIMEOUT,
        )

    async def _download_image_base64(self, url: str) -> tuple[str, str]:
        """
        Helper to convert an image URL or data URI to base64 and media type.
        """
        if url.startswith("data:"):
            try:
                # Format: data:image/jpeg;base64,/9j/4AAQSkZJRg...
                header, encoded = url.split(";base64,")
                media_type = header.replace("data:", "")
                return encoded, media_type
            except Exception as e:
                raise ValueError(f"Invalid data URI format: {e}")

        # Public URL, download via HTTP
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(url, timeout=10.0)
                response.raise_for_status()
                media_type = response.headers.get("content-type", "image/jpeg")
                encoded = base64.b64encode(response.content).decode("utf-8")
                return encoded, media_type
        except Exception as e:
            raise ValueError(f"Failed to fetch image from URL {url}: {e}")

    async def _map_messages(self, messages: List[MessageDTO]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Maps standard message list to Claude format.
        Extracts system prompts and maps content (including vision/tool blocks).
        """
        system_prompt = None
        mapped_messages = []

        for msg in messages:
            if msg.role in ["system", "developer"]:
                # Anthropic expects system prompt at the top level
                system_prompt = msg.content if isinstance(msg.content, str) else str(msg.content)
                continue

            role = "user" if msg.role in ["user", "tool"] else "assistant"
            
            # Map content
            content_blocks = []

            if msg.role == "tool":
                # Claude tool results must be submitted in a user role block with type tool_result
                content_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content if isinstance(msg.content, str) else str(msg.content)
                })
            elif isinstance(msg.content, list):
                for item in msg.content:
                    if isinstance(item, dict):
                        if item.get("type") == "image_url":
                            img_url = item["image_url"]["url"]
                            try:
                                b64_data, media_type = await self._download_image_base64(img_url)
                                content_blocks.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": b64_data,
                                    }
                                })
                            except Exception as e:
                                logger.error(f"Error loading image for Claude: {e}")
                                # Fallback to text representation
                                content_blocks.append({
                                    "type": "text",
                                    "text": f"[Image load failed: {img_url}]"
                                })
                        elif item.get("type") == "text":
                            content_blocks.append({
                                "type": "text",
                                "text": item["text"]
                            })
                    else:
                        content_blocks.append({
                            "type": "text",
                            "text": str(item)
                        })
            else:
                content_blocks.append({
                    "type": "text",
                    "text": msg.content
                })

            # Check if this assistant message is sending tool calls
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    import json
                    try:
                        args = json.loads(tc.arguments)
                    except Exception:
                        args = tc.arguments
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function_name,
                        "input": args
                    })

            mapped_messages.append({
                "role": role,
                "content": content_blocks
            })

        return system_prompt, mapped_messages

    def _map_tools(self, request: ChatRequest) -> Optional[List[Dict[str, Any]]]:
        if not request.tools:
            return None
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in request.tools
        ]

    async def chat(self, request: ChatRequest, timeout: Optional[float] = None) -> ChatResponse:
        async def _run():
            start_time = time.perf_counter()
            system_prompt, messages = await self._map_messages(request.messages)
            
            kwargs: Dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "max_tokens": request.max_tokens or 4096,  # Claude requires max_tokens
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.top_p is not None:
                kwargs["top_p"] = request.top_p

            tools = self._map_tools(request)
            if tools:
                kwargs["tools"] = tools
                if request.tool_choice:
                    # Map tool choice. Anthropic has different format, e.g. {"type": "auto"}
                    if request.tool_choice == "auto":
                        kwargs["tool_choice"] = {"type": "auto"}
                    elif request.tool_choice == "any":
                        kwargs["tool_choice"] = {"type": "any"}
                    else:
                        kwargs["tool_choice"] = {"type": "tool", "name": request.tool_choice}

            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            response = await self.client.messages.create(
                **kwargs, timeout=actual_timeout
            )
            latency = (time.perf_counter() - start_time) * 1000

            # Parse responses
            text_content = ""
            tool_calls = []

            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                elif block.type == "tool_use":
                    import json
                    tool_calls.append(
                        ToolCallDTO(
                            id=block.id,
                            type="function",
                            function_name=block.name,
                            arguments=json.dumps(block.input),
                        )
                    )

            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            total_tokens = prompt_tokens + completion_tokens
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

            return ChatResponse(
                id=response.id,
                model=response.model,
                provider="claude",
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

        return await execute_with_retry("claude", _run, max_retries=ai_settings.MAX_RETRIES)

    async def stream(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        system_prompt, messages = await self._map_messages(request.messages)
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p

        actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT

        try:
            async with self.client.messages.stream(**kwargs, timeout=actual_timeout) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield StreamingChunkDTO(
                            id=stream.current_message_id or "claude-chunk",
                            model=request.model,
                            provider="claude",
                            content=event.delta.text,
                        )
                    
                # Yield final usage chunk if available
                final_msg = await stream.get_final_message()
                prompt_tokens = final_msg.usage.input_tokens
                completion_tokens = final_msg.usage.output_tokens
                total_tokens = prompt_tokens + completion_tokens
                cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

                yield StreamingChunkDTO(
                    id=final_msg.id,
                    model=request.model,
                    provider="claude",
                    content="",
                    finish_reason=final_msg.stop_reason,
                    usage=UsageDTO(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        cost=cost,
                    )
                )
        except Exception as e:
            raise map_provider_exception("claude", e)

    async def embeddings(
        self, request: EmbeddingRequest, timeout: Optional[float] = None
    ) -> EmbeddingResponse:
        # Anthropic does not support embedding models
        raise NotImplementedError("Embeddings are not supported by the Anthropic Claude provider.")

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            # Low cost health query. We can use a simple message check
            await self.client.messages.create(
                model="claude-3-5-haiku-latest",
                messages=[{"role": "user", "content": "Ping"}],
                max_tokens=1,
                timeout=5.0,
            )
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="healthy",
                provider="claude",
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="unhealthy",
                provider="claude",
                latency_ms=latency,
                details=str(e),
            )

    async def list_models(self) -> List[str]:
        from app.core.model_registry import ModelRegistry
        return [m.name for m in ModelRegistry.list_models_by_provider("claude")]

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: Optional[float] = None
    ) -> ChatResponse:
        """
        Generate structured output adhering to a specific JSON schema/Pydantic model.
        Implemented for Claude by supplying the target schema as a tool definition
        and forcing Claude to call that tool.
        """
        import json
        schema_name = "structured_output_schema"
        
        # Extract schema parameters
        if hasattr(response_schema, "model_json_schema"):
            schema_params = response_schema.model_json_schema()
            schema_name = response_schema.__name__
        elif hasattr(response_schema, "schema"):
            schema_params = response_schema.schema()
            schema_name = response_schema.__name__
        else:
            schema_params = response_schema

        # Convert/ensure it's a dict
        if not isinstance(schema_params, dict):
            raise ValueError("response_schema must be a valid Pydantic model or JSON Schema dict.")

        # Create structured output request using Claude tool calling
        structured_tool = {
            "name": schema_name,
            "description": f"Outputs data adhering to the {schema_name} schema.",
            "input_schema": schema_params,
        }

        async def _run():
            start_time = time.perf_counter()
            system_prompt, messages = await self._map_messages(request.messages)

            kwargs: Dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "max_tokens": request.max_tokens or 4096,
                "tools": [structured_tool],
                "tool_choice": {"type": "tool", "name": schema_name},
            }
            if system_prompt:
                kwargs["system"] = system_prompt
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.top_p is not None:
                kwargs["top_p"] = request.top_p

            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            response = await self.client.messages.create(
                **kwargs, timeout=actual_timeout
            )
            latency = (time.perf_counter() - start_time) * 1000

            # Find the tool call chunk
            json_output = ""
            for block in response.content:
                if block.type == "tool_use" and block.name == schema_name:
                    json_output = json.dumps(block.input)
                    break

            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            total_tokens = prompt_tokens + completion_tokens
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

            return ChatResponse(
                id=response.id,
                model=response.model,
                provider="claude",
                message=MessageDTO(
                    role="assistant",
                    content=json_output,
                ),
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                ),
                latency_ms=latency,
            )

        return await execute_with_retry("claude", _run, max_retries=ai_settings.MAX_RETRIES)

    async def tool_call(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> ChatResponse:
        return await self.chat(request, timeout)
