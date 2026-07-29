import time
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx
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
from app.utils.ai_error_handler import map_provider_exception, execute_with_retry
from app.utils.token_utils import calculate_cost, calculate_tokens

logger = logging.getLogger("ai_service")

class OllamaProvider(BaseLLMProvider):
    """
    Ollama Provider implementation communicating with local Ollama service.
    Handles Chat, Streaming, Embeddings, Tool Calling, and JSON Structured Outputs.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or ai_settings.OLLAMA_URL).rstrip("/")

    def _map_messages(self, messages: List[MessageDTO]) -> List[Dict[str, Any]]:
        mapped = []
        for msg in messages:
            msg_dict: Dict[str, Any] = {"role": msg.role}
            
            # Map content
            if isinstance(msg.content, list):
                # Map vision contents if present (Ollama handles image base64 directly in "images" array)
                images = []
                text_parts = []
                for item in msg.content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        img_url = item["image_url"]["url"]
                        if img_url.startswith("data:image/"):
                            # Extract base64
                            b64_data = img_url.split(";base64,")[1]
                            images.append(b64_data)
                        else:
                            # Ollama only supports base64 strings directly in the images key.
                            # We can keep it as is if it's already base64, otherwise skip or log.
                            pass
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                    else:
                        text_parts.append(str(item))
                msg_dict["content"] = " ".join(text_parts)
                if images:
                    msg_dict["images"] = images
            else:
                msg_dict["content"] = msg.content

            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.function_name,
                            "arguments": json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                        }
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
            
            # Options mapping
            options: Dict[str, Any] = {}
            if request.temperature is not None:
                options["temperature"] = request.temperature
            if request.top_p is not None:
                options["top_p"] = request.top_p
            if request.max_tokens is not None:
                options["num_predict"] = request.max_tokens

            payload: Dict[str, Any] = {
                "model": request.model,
                "messages": self._map_messages(request.messages),
                "stream": False,
                "options": options,
            }

            if request.json_mode:
                payload["format"] = "json"

            tools = self._map_tools(request)
            if tools:
                payload["tools"] = tools

            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=actual_timeout
                )
                response.raise_for_status()
                data = response.json()

            latency = (time.perf_counter() - start_time) * 1000
            
            # Parse response message
            response_msg = data.get("message", {})
            content = response_msg.get("content", "")
            
            # Parse tool calls
            tool_calls = None
            raw_tool_calls = response_msg.get("tool_calls", [])
            if raw_tool_calls:
                tool_calls = []
                for idx, tc in enumerate(raw_tool_calls):
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    tool_calls.append(
                        ToolCallDTO(
                            id=f"ollama-tc-{idx}",
                            type="function",
                            function_name=func.get("name", ""),
                            arguments=json.dumps(args) if isinstance(args, dict) else str(args)
                        )
                    )

            # Map token usage
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)

            return ChatResponse(
                id=f"ollama-{int(time.time())}",
                model=request.model,
                provider="ollama",
                message=MessageDTO(
                    role="assistant",
                    content=content,
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

        return await execute_with_retry("ollama", _run, max_retries=ai_settings.MAX_RETRIES)

    async def stream(
        self, request: ChatRequest, timeout: Optional[float] = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        options: Dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.top_p is not None:
            options["top_p"] = request.top_p
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": self._map_messages(request.messages),
            "stream": True,
            "options": options,
        }

        if request.json_mode:
            payload["format"] = "json"

        actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=actual_timeout
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        
                        usage = None
                        if data.get("done", False):
                            prompt_tokens = data.get("prompt_eval_count", 0)
                            completion_tokens = data.get("eval_count", 0)
                            total_tokens = prompt_tokens + completion_tokens
                            usage = UsageDTO(
                                prompt_tokens=prompt_tokens,
                                completion_tokens=completion_tokens,
                                total_tokens=total_tokens,
                                cost=0.0
                            )

                        yield StreamingChunkDTO(
                            id=f"ollama-chunk-{int(time.time())}",
                            model=request.model,
                            provider="ollama",
                            content=content,
                            finish_reason="stop" if data.get("done", False) else None,
                            usage=usage,
                        )
        except Exception as e:
            raise map_provider_exception("ollama", e)

    async def embeddings(
        self, request: EmbeddingRequest, timeout: Optional[float] = None
    ) -> EmbeddingResponse:
        async def _run():
            # Handle list of inputs or single input
            inputs = request.input if isinstance(request.input, list) else [request.input]
            embeddings = []
            
            actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
            async with httpx.AsyncClient() as client:
                for text in inputs:
                    payload = {
                        "model": request.model,
                        "prompt": text,
                    }
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json=payload,
                        timeout=actual_timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                    embeddings.append(data["embedding"])

            # Locally hosted, cost is 0
            prompt_tokens = sum(calculate_tokens(text, request.model) for text in inputs)
            return EmbeddingResponse(
                model=request.model,
                provider="ollama",
                embeddings=embeddings,
                usage=UsageDTO(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    total_tokens=prompt_tokens,
                    cost=0.0,
                ),
            )

        return await execute_with_retry("ollama", _run, max_retries=ai_settings.MAX_RETRIES)

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                # Check root or tags endpoint
                response = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                response.raise_for_status()
                latency = (time.perf_counter() - start_time) * 1000
                return HealthDTO(
                    status="healthy",
                    provider="ollama",
                    latency_ms=latency,
                )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="unhealthy",
                provider="ollama",
                latency_ms=latency,
                details=str(e),
            )

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            # Fallback to model registry if Ollama is offline
            from app.core.model_registry import ModelRegistry
            return [m.name for m in ModelRegistry.list_models_by_provider("ollama")]

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: Optional[float] = None
    ) -> ChatResponse:
        """
        Generate structured output. For Ollama, we set format="json" and append schema
        instructions to the prompt.
        """
        # Get JSON schema representation
        if hasattr(response_schema, "model_json_schema"):
            schema_desc = json.dumps(response_schema.model_json_schema())
        elif hasattr(response_schema, "schema"):
            schema_desc = json.dumps(response_schema.schema())
        else:
            schema_desc = str(response_schema)

        # Clone and inject structured format instruction to prompt
        request_copy = ChatRequest(**request.model_dump())
        request_copy.json_mode = True
        
        # Inject system/user instruction to match schema
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
