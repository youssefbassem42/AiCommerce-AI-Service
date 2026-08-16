"""Phase 1 tests: conversation-aware intent resolution.

Exit criteria (spec):
- "$50", "black", "15 inch", "yes" continue the active shopping/support flow.
- "tell me about your oven" -> product_information (NOT sales/budget questions).
- "what is your return policy" -> support.
- "I want to talk to a human." -> support (decision engine owns escalation).
- "mouse and keyboard" / "phone + charger" -> bundle.
- "i want a laptop with 16gb ram and 1tb ssd" -> NOT bundle (spec detail).
- Escalation labels never survive the resolver.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.application.context.intent_resolver import (
    detect_bundle_request,
    detect_continuation,
    resolve_intent,
)


@pytest.mark.asyncio
class TestDeterministicRouting:
    async def test_human_request_routes_to_support(self):
        for phrase in [
            "I want to talk to a human.",
            "Please escalate this",
            "Connect me to a real agent",
        ]:
            result = await resolve_intent(phrase)
            assert result.intent == "support", phrase
            assert result.source in ("deterministic", "deterministic-human")

    async def test_policy_keyword_routes_to_support(self):
        result = await resolve_intent("What is your return policy?")
        assert result.intent == "support"

    async def test_product_information_phrasing(self):
        for phrase in [
            "Tell me about your oven",
            "What are the dimensions of the laptop?",
            "What specs does the phone have?",
            "Does it come with a keyboard?",
            "How big is the TV?",
            "Is it available in black?",
        ]:
            result = await resolve_intent(phrase)
            assert result.intent == "product_information", phrase

    async def test_bundle_signals(self):
        for phrase in [
            "I want a bundle deal",
            "Mouse and keyboard",
            "phone + charger",
            "I'm looking for a complete gaming setup",
        ]:
            result = await resolve_intent(phrase)
            assert result.intent == "bundle", phrase

    async def test_spec_detail_is_not_bundle(self):
        assert detect_bundle_request("i want a laptop with 16gb ram and 1tb ssd") is False
        result = await resolve_intent("I want a laptop with 16gb ram and 1tb ssd", previous_intent="sales")
        assert result.intent != "bundle"


@pytest.mark.asyncio
class TestContinuation:
    async def test_budget_continues_flow(self):
        result = await resolve_intent("$50", previous_intent="sales")
        assert result.intent == "sales"
        assert result.source == "continuation"

    async def test_color_continues_flow(self):
        result = await resolve_intent("black", previous_intent="recommendation")
        assert result.intent == "recommendation"

    async def test_affirmation_continues_flow(self):
        result = await resolve_intent("yes", previous_intent="bundle")
        assert result.intent == "bundle"

    async def test_use_case_continues_flow(self):
        result = await resolve_intent("for gaming", previous_intent="recommendation")
        assert result.intent == "recommendation"

    async def test_continuation_without_previous_uses_llm(self):
        with patch(
            "app.application.context.intent_resolver.classify_intent",
            AsyncMock(return_value=("general", 0.5)),
        ):
            result = await resolve_intent("$50")
        assert result.intent == "general"
        assert result.source == "llm"

    async def test_new_topic_overrides_continuation(self):
        result = await resolve_intent("what is your return policy", previous_intent="recommendation")
        assert result.intent == "support"

    async def test_detect_continuation_helpers(self):
        assert detect_continuation("under 100", "sales")
        assert detect_continuation("the second one", "recommendation")
        assert not detect_continuation("tell me about your oven", "sales")


@pytest.mark.asyncio
class TestEscalationNormalization:
    async def test_escalation_label_normalized_to_support(self):
        with patch(
            "app.application.context.intent_resolver.classify_intent",
            AsyncMock(return_value=("escalation", 0.9)),
        ):
            result = await resolve_intent("I'm furious and nobody is helping.")
        assert result.intent == "support"
        assert result.source == "llm-normalized"

    async def test_never_returns_escalation(self):
        with patch(
            "app.application.context.intent_resolver.classify_intent",
            AsyncMock(return_value=("escalation", 0.95)),
        ):
            result = await resolve_intent("whatever")
        assert result.intent != "escalation"


@pytest.mark.asyncio
class TestFallback:
    async def test_classifier_failure_keeps_active_flow(self):
        with patch(
            "app.application.context.intent_resolver.classify_intent",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await resolve_intent("something", previous_intent="recommendation")
        assert result.intent == "recommendation"
        assert result.source == "fallback"

    async def test_classifier_failure_falls_back_to_general(self):
        with patch(
            "app.application.context.intent_resolver.classify_intent",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await resolve_intent("something")
        assert result.intent == "general"
