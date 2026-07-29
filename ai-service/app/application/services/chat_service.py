import time
import uuid
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    MessageDTO,
    StreamingChunkDTO,
    UsageDTO,
)
from app.application.services.conversation_service import ConversationService
from app.core.ai_settings import ai_settings
from app.core.model_registry import ModelRegistry
from app.utils.token_utils import calculate_tokens, calculate_cost
from app.core.ai_exceptions import AIException, ProviderUnavailableException, RateLimitException

logger = logging.getLogger("ai_service")

class ChatService:
    """
    Core AI Orchestrator Service.
    Coordinates chat, streaming, structured output, and embeddings.
    Implements tracing, rate limit checking, cost calculations, metrics logging,
    and automatic failover/fallback to alternative providers.
    """

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        conversation_service: Optional[ConversationService] = None,
    ):
        self.provider_factory = provider_factory
        self.conversation_service = conversation_service

    def _generate_correlation_id(self) -> str:
        return str(uuid.uuid4())

    def _log_metrics(
        self,
        correlation_id: str,
        provider: str,
        model: str,
        latency_ms: float,
        usage: UsageDTO,
        action: str = "chat",
        error: Optional[str] = None,
    ):
        """
        Log structured metrics for tracking and dashboarding.
        """
        log_data = {
            "request_id": correlation_id,
            "action": action,
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": usage.cost,
            "status": "error" if error else "success",
        }
        if error:
            log_data["error"] = error
            logger.error(f"[AI Metrics Error] {log_data}")
        else:
            logger.info(f"[AI Metrics] {log_data}")

    async def chat(
        self,
        request: ChatRequest,
        conversation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        fallbacks: Optional[List[str]] = None,
    ) -> ChatResponse:
        """
        Generate completion response, automatically trying fallback providers if the main call fails.
        """
        corr_id = correlation_id or self._generate_correlation_id()
        
        # Inject conversation history if conversation_id is provided
        if conversation_id and self.conversation_service:
            history = await self.conversation_service.get_conversation_history(conversation_id)
            if history:
                # Merge history messages before current messages
                request.messages = history + request.messages

        model_info = ModelRegistry.get_model_info(request.model)
        primary_provider = model_info.provider if model_info else ai_settings.DEFAULT_PROVIDER
        
        # Build queue of providers to try (primary first, then fallbacks)
        provider_queue = [primary_provider]
        if fallbacks:
            for f in fallbacks:
                if f != primary_provider:
                    provider_queue.append(f)

        last_exception = None
        for provider_name in provider_queue:
            try:
                provider = self.provider_factory.get_provider(provider_name)
                
                # Check capability
                if model_info and not model_info.capabilities.streaming and request.stream:
                    raise AIException(f"Streaming not supported for model {request.model}", 400)

                start_time = time.perf_counter()
                
                # Perform call
                response = await provider.chat(request)
                
                latency = (time.perf_counter() - start_time) * 1000
                response.latency_ms = latency

                # Log metrics
                self._log_metrics(corr_id, provider_name, request.model, latency, response.usage, "chat")

                # Save interaction history
                if conversation_id and self.conversation_service:
                    # User message is the last message sent by user in request
                    user_msg = [m for m in request.messages if m.role == "user"][-1]
                    await self.conversation_service.save_interaction(
                        conversation_id=conversation_id,
                        user_message=user_msg,
                        assistant_message=response.message,
                        usage=response.usage,
                        latency_ms=latency,
                    )

                return response

            except (ProviderUnavailableException, RateLimitException) as e:
                logger.warning(f"Provider '{provider_name}' failed with transient error: {e}. Trying fallback...")
                last_exception = e
            except Exception as e:
                logger.error(f"Provider '{provider_name}' failed with unexpected error: {e}.")
                last_exception = e

        # If all fail
        self._log_metrics(
            corr_id,
            primary_provider,
            request.model,
            0.0,
            UsageDTO(),
            "chat",
            error=str(last_exception),
        )
        raise last_exception or AIException("Chat generation failed for all configured providers.")

    async def stream(
        self,
        request: ChatRequest,
        conversation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        """
        Stream response from the provider.
        """
        corr_id = correlation_id or self._generate_correlation_id()
        model_info = ModelRegistry.get_model_info(request.model)
        provider_name = model_info.provider if model_info else ai_settings.DEFAULT_PROVIDER
        
        provider = self.provider_factory.get_provider(provider_name)
        
        start_time = time.perf_counter()
        accumulated_content = []
        prompt_tokens = sum(calculate_tokens(m.content if isinstance(m.content, str) else str(m.content), request.model) for m in request.messages)

        try:
            async for chunk in provider.stream(request):
                if chunk.content:
                    accumulated_content.append(chunk.content)
                yield chunk
                
            latency = (time.perf_counter() - start_time) * 1000
            
            # Log final usage metrics
            final_content = "".join(accumulated_content)
            completion_tokens = calculate_tokens(final_content, request.model)
            total_tokens = prompt_tokens + completion_tokens
            cost = calculate_cost(prompt_tokens, completion_tokens, request.model)
            
            usage = UsageDTO(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost=cost,
            )
            self._log_metrics(corr_id, provider_name, request.model, latency, usage, "stream")

            # Save to conversation memory if applicable
            if conversation_id and self.conversation_service:
                user_msg = [m for m in request.messages if m.role == "user"][-1]
                assistant_msg = MessageDTO(role="assistant", content=final_content)
                await self.conversation_service.save_interaction(
                    conversation_id=conversation_id,
                    user_message=user_msg,
                    assistant_message=assistant_msg,
                    usage=usage,
                    latency_ms=latency,
                )

        except Exception as e:
            self._log_metrics(corr_id, provider_name, request.model, 0.0, UsageDTO(), "stream", error=str(e))
            raise e

    async def embeddings(
        self,
        request: EmbeddingRequest,
        correlation_id: Optional[str] = None,
    ) -> EmbeddingResponse:
        corr_id = correlation_id or self._generate_correlation_id()
        model_info = ModelRegistry.get_model_info(request.model)
        provider_name = model_info.provider if model_info else ai_settings.DEFAULT_PROVIDER
        
        provider = self.provider_factory.get_provider(provider_name)
        start_time = time.perf_counter()
        
        try:
            response = await provider.embeddings(request)
            latency = (time.perf_counter() - start_time) * 1000
            self._log_metrics(corr_id, provider_name, request.model, latency, response.usage, "embeddings")
            return response
        except Exception as e:
            self._log_metrics(corr_id, provider_name, request.model, 0.0, UsageDTO(), "embeddings", error=str(e))
            raise e

    async def structured_output(
        self,
        request: ChatRequest,
        response_schema: Any,
        correlation_id: Optional[str] = None,
    ) -> ChatResponse:
        corr_id = correlation_id or self._generate_correlation_id()
        model_info = ModelRegistry.get_model_info(request.model)
        provider_name = model_info.provider if model_info else ai_settings.DEFAULT_PROVIDER
        
        provider = self.provider_factory.get_provider(provider_name)
        start_time = time.perf_counter()
        
        try:
            response = await provider.structured_output(request, response_schema)
            latency = (time.perf_counter() - start_time) * 1000
            response.latency_ms = latency
            self._log_metrics(corr_id, provider_name, request.model, latency, response.usage, "structured_output")
            return response
        except Exception as e:
            self._log_metrics(corr_id, provider_name, request.model, 0.0, UsageDTO(), "structured_output", error=str(e))
            raise e

    async def tool_call(
        self,
        request: ChatRequest,
        correlation_id: Optional[str] = None,
    ) -> ChatResponse:
        corr_id = correlation_id or self._generate_correlation_id()
        model_info = ModelRegistry.get_model_info(request.model)
        provider_name = model_info.provider if model_info else ai_settings.DEFAULT_PROVIDER
        
        provider = self.provider_factory.get_provider(provider_name)
        start_time = time.perf_counter()
        
        try:
            response = await provider.tool_call(request)
            latency = (time.perf_counter() - start_time) * 1000
            response.latency_ms = latency
            self._log_metrics(corr_id, provider_name, request.model, latency, response.usage, "tool_call")
            return response
        except Exception as e:
            self._log_metrics(corr_id, provider_name, request.model, 0.0, UsageDTO(), "tool_call", error=str(e))
            raise e
