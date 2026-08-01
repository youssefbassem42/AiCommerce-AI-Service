from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.recommendation.dto.recommendation_dto import RecommendationResponse
from app.application.services.orchestration_service import OrchestrationService
from app.infrastructure.providers.factory import LLMProviderFactory


@pytest.fixture
def llm():
    provider = AsyncMock()

    def structured_side_effect(request, response_schema):
        prompt = request.messages[-1].content
        if "classify" in prompt.lower():
            content = '{"intent": "recommendation", "confidence": 0.9}'
        else:
            content = '{"key_topics": [], "customer_preferences": [], "store_facts": [], "sentiment": "neutral"}'
        response = MagicMock()
        response.message.content = content
        return response

    provider.structured_output.side_effect = structured_side_effect

    def chat_side_effect(request):
        response = MagicMock()
        response.message.content = "Fallback answer."
        return response

    provider.chat.side_effect = chat_side_effect
    return provider


@pytest.fixture
def recommendation_service():
    service = AsyncMock()
    service.recommend.return_value = RecommendationResponse(
        query="recommend a phone",
        store_id="store_1",
        customer_id="customer_1",
        rationale="Top pick: Phone X.",
    )
    return service


@pytest.fixture
def bundle_service():
    return AsyncMock()


@pytest.fixture
def conversation_service():
    service = AsyncMock()
    service.get_conversation_history.return_value = []
    service.save_interaction.return_value = None
    return service


@pytest.fixture
def memory_repo():
    return AsyncMock()


class TestOrchestrationService:
    async def test_chat_runs_coordinator_workflow(
        self, llm, recommendation_service, bundle_service, conversation_service, memory_repo
    ):
        service = OrchestrationService(
            provider_factory=LLMProviderFactory(),
            conversation_service=conversation_service,
            memory_repo=memory_repo,
            recommendation_service=recommendation_service,
            bundle_service=bundle_service,
            llm=llm,
        )

        response = await service.chat(
            user_input="recommend a phone",
            store_id="store_1",
            customer_id="customer_1",
            conversation_id="convo_1",
        )

        assert response.message.content == "Top pick: Phone X."
        assert response.metadata["intent"] == "recommendation"
        recommendation_service.recommend.assert_awaited_once()

    async def test_chat_graceful_fallback_for_coming_soon(
        self, llm, recommendation_service, bundle_service, conversation_service, memory_repo
    ):
        def structured_side_effect(request, response_schema):
            prompt = request.messages[-1].content
            if "classify" in prompt.lower():
                content = '{"intent": "marketing", "confidence": 0.85}'
            else:
                content = '{"key_topics": [], "customer_preferences": [], "store_facts": [], "sentiment": "negative"}'
            response = MagicMock()
            response.message.content = content
            return response

        llm.structured_output.side_effect = structured_side_effect

        service = OrchestrationService(
            provider_factory=LLMProviderFactory(),
            conversation_service=conversation_service,
            memory_repo=memory_repo,
            recommendation_service=recommendation_service,
            bundle_service=bundle_service,
            llm=llm,
        )

        response = await service.chat(user_input="create a campaign", store_id="store_1")

        assert response.message.content == "Fallback answer."
        assert response.metadata["intent"] == "marketing"

    async def test_workflow_is_built_once(self, llm, recommendation_service, bundle_service, memory_repo):
        service = OrchestrationService(
            provider_factory=LLMProviderFactory(),
            memory_repo=memory_repo,
            recommendation_service=recommendation_service,
            bundle_service=bundle_service,
            llm=llm,
        )

        workflow = service.workflow

        assert workflow is service.workflow
