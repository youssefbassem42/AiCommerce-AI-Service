from typing import Any

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import StreamingResponse

from app.api.ai.dependencies import get_ai_service, get_provider_factory, get_store_context
from app.api.ai.schemas import (
    ChatRequestSchema,
    ChatResponseSchema,
    EmbeddingResponseSchema,
    EmbeddingSchema,
    HealthResponseSchema,
    MessageSchema,
    ProviderResponseSchema,
    StreamingSchema,
    StructuredOutputSchema,
)
from app.application.dto.ai_dto import ChatRequest, EmbeddingRequest
from app.application.services.chat_service import ChatService
from app.core.ai_settings import ai_settings
from app.core.model_registry import ModelRegistry
from app.infrastructure.providers.factory import LLMProviderFactory

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])

ECOMMERCE_SYSTEM_PROMPT = (
    "You are an AI assistant for an e-commerce SaaS platform called DigitalHippo. "
    "You help store owners and customers with product inquiries, order management, "
    "catalog questions, promo codes, discounts, gift cards, shipping, and general "
    "store operations. When discussing technical integration, refer to the store's "
    "connected API capabilities. If you don't know something, say so honestly. "
    "Always be helpful, concise, and focused on e-commerce tasks."
)


def _inject_ecommerce_system_message(messages: list[MessageSchema]) -> list[MessageSchema]:
    has_system = any(m.role == "system" for m in messages)
    if has_system:
        return messages
    return [MessageSchema(role="system", content=ECOMMERCE_SYSTEM_PROMPT)] + messages


@router.post("/chat", response_model=ChatResponseSchema)
async def chat(
    request: Request,
    payload: ChatRequestSchema,
    conversation_id: str | None = None,
    ai_service: ChatService = Depends(get_ai_service),
) -> Any:
    """
    Generate chat completion response.
    Supports temperature, top_p, max_tokens, json_mode, and automatic fallbacks.
    Injects e-commerce system prompt if no system message is present.
    Chat traffic flows through the Phase 01 coordinator + conversation workflow.
    """
    payload.messages = _inject_ecommerce_system_message(payload.messages)
    request_dto = ChatRequest(**payload.model_dump())
    store_id, customer_id = get_store_context(request)
    response_dto = await ai_service.chat(
        request_dto,
        conversation_id=conversation_id,
        store_id=store_id,
        customer_id=customer_id,
    )
    return response_dto


@router.post("/chat/stream")
async def chat_stream(
    request: StreamingSchema, conversation_id: str | None = None, ai_service: ChatService = Depends(get_ai_service)
) -> StreamingResponse:
    """
    Stream chat completion response back in SSE (Server-Sent Events) format.
    Injects e-commerce system prompt if no system message is present.
    """
    request.messages = _inject_ecommerce_system_message(request.messages)
    request_dto = ChatRequest(**request.model_dump())

    async def event_generator():
        async for chunk in ai_service.stream(request_dto, conversation_id=conversation_id):
            yield f"data: {chunk.model_dump_json()}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat/structured", response_model=ChatResponseSchema)
async def chat_structured(request: StructuredOutputSchema, ai_service: ChatService = Depends(get_ai_service)) -> Any:
    """
    Generate structured outputs matching the schema_definition.
    """
    # Map back message format
    request_dto = ChatRequest(
        messages=[m.model_dump() for m in request.messages],  # type: ignore
        model=request.model,
        json_mode=True,
    )
    response_dto = await ai_service.structured_output(request_dto, request.schema_definition)
    return response_dto


@router.post("/chat/tools", response_model=ChatResponseSchema)
async def chat_tools(request: ChatRequestSchema, ai_service: ChatService = Depends(get_ai_service)) -> Any:
    """
    Chat completion with tool/function definitions.
    """
    request_dto = ChatRequest(**request.model_dump())
    response_dto = await ai_service.tool_call(request_dto)
    return response_dto


@router.post("/embeddings", response_model=EmbeddingResponseSchema)
async def embeddings(request: EmbeddingSchema, ai_service: ChatService = Depends(get_ai_service)) -> Any:
    """
    Generate text embeddings.
    """
    request_dto = EmbeddingRequest(**request.model_dump())
    response_dto = await ai_service.embeddings(request_dto)
    return response_dto


@router.get("/models", response_model=list[dict[str, Any]])
async def list_models() -> list[dict[str, Any]]:
    """
    List all supported models across all providers in the model registry.
    """
    models = ModelRegistry.list_all_models()
    return [m.model_dump() for m in models]


@router.get("/providers", response_model=list[ProviderResponseSchema])
async def list_providers() -> list[Any]:
    """
    List all supported providers with their registered models and capabilities.
    """
    providers = ["openai", "azure", "gemini", "claude", "ollama", "deepseek", "mistral"]
    result = []
    for p in providers:
        models = ModelRegistry.list_models_by_provider(p)
        model_names = [m.name for m in models]

        # Aggregate general capabilities
        capabilities = {
            "vision": False,
            "json_mode": False,
            "tool_calling": False,
            "streaming": False,
            "embedding": False,
        }
        for m in models:
            if m.capabilities.vision:
                capabilities["vision"] = True
            if m.capabilities.json_mode:
                capabilities["json_mode"] = True
            if m.capabilities.tool_calling:
                capabilities["tool_calling"] = True
            if m.capabilities.streaming:
                capabilities["streaming"] = True
            if m.capabilities.embedding:
                capabilities["embedding"] = True

        result.append({"provider": p, "supported_models": model_names, "capabilities": capabilities})
    return result


@router.get("/health", response_model=HealthResponseSchema)
async def health(factory: LLMProviderFactory = Depends(get_provider_factory)) -> Any:
    """
    Health check for default configured AI provider.
    """
    provider = factory.get_provider(ai_settings.DEFAULT_PROVIDER)
    health_dto = await provider.health_check()
    return health_dto


@router.get("/provider/{provider}/models", response_model=list[str])
async def provider_models(
    provider: str = Path(..., description="The name of the AI provider"),
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> list[str]:
    """
    List all supported models for a specific AI provider.
    """
    prov = factory.get_provider(provider)
    return await prov.list_models()


@router.get("/provider/{provider}/health", response_model=HealthResponseSchema)
async def provider_health(
    provider: str = Path(..., description="The name of the AI provider"),
    factory: LLMProviderFactory = Depends(get_provider_factory),
) -> Any:
    """
    Run the health check for a specific AI provider.
    """
    prov = factory.get_provider(provider)
    health_dto = await prov.health_check()
    return health_dto
