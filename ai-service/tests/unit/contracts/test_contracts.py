"""Phase 0 canonical contracts tests: intent vocabulary, product/bundle payloads,
escalation decisions, turn trace, and the AI response schema."""

from decimal import Decimal

from app.application.contracts import (
    COMING_SOON_INTENTS,
    EXECUTABLE_INTENTS,
    AITurnContract,
    BundlePayload,
    ConversationTurnTrace,
    EscalationDecision,
    Intent,
    ProductPayload,
    build_escalation_decision,
    bundle_payload_from_candidates,
    coerce_intent,
    product_card_to_payload,
)
from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    DiscountInfo,
    ProductCard,
    ProductSpecValue,
)


class TestIntentVocabulary:
    def test_enum_values_are_canonical(self):
        assert Intent.SALES == "sales"
        assert Intent.SUPPORT == "support"
        assert Intent.BUNDLE == "bundle"
        assert Intent.RECOMMENDATION == "recommendation"
        assert Intent.ESCALATION == "escalation"
        assert Intent.GENERAL == "general"

    def test_executable_and_coming_soon_sets(self):
        assert {i.value for i in EXECUTABLE_INTENTS} == {"bundle", "recommendation", "sales", "support", "escalation"}
        assert {i.value for i in COMING_SOON_INTENTS} == {"marketing", "analytics"}

    def test_coerce_intent_normalizes(self):
        assert coerce_intent("  Sales ") is Intent.SALES
        assert coerce_intent("RECOMMENDATION") is Intent.RECOMMENDATION
        assert coerce_intent("made-up-intent") is None
        assert coerce_intent(None) is None
        assert coerce_intent("") is None


class TestProductPayload:
    def test_product_card_conversion(self):
        card = ProductCard(
            product_id="p-1",
            title="Wireless Mouse",
            price=Decimal("49.99"),
            currency="USD",
            image_url="https://cdn.example/mouse.jpg",
            specs=[ProductSpecValue(name="Color", value="Black")],
            match_reasons=["Matches 'wireless'"],
        )
        payload = product_card_to_payload(card)
        assert isinstance(payload, ProductPayload)
        assert payload.product_id == "p-1"
        assert payload.price == "49.99"
        assert payload.specs[0].name == "Color"
        assert payload.specs[0].category == "general"

    def test_invalid_card_returns_none(self):
        assert product_card_to_payload(None) is None
        assert product_card_to_payload(object()) is None

    def test_contract_serializes_consumer_safe(self):
        card = ProductCard(product_id="p-2", title="Headphones", price=Decimal("99"))
        dump = product_card_to_payload(card).model_dump()
        assert dump["product_id"] == "p-2"
        assert dump["price"] == "99"
        assert set(dump) >= {"product_id", "title", "price", "currency", "image_url", "product_url", "specs"}


class TestBundlePayload:
    def test_bundle_from_candidates(self):
        candidate = BundleCandidate(
            products=[
                DiscountInfo(
                    product_id="p-1",
                    product_title="Mouse",
                    original_price=Decimal("20"),
                    discount_pct=10.0,
                    price_after_discount=Decimal("18"),
                )
            ],
            total_original=Decimal("20"),
            total_discount=Decimal("2"),
            total_after_discount=Decimal("18"),
            within_budget=True,
            promo_code=None,
        )
        payload = bundle_payload_from_candidates([candidate])
        assert isinstance(payload, BundlePayload)
        assert payload.items[0].product_id == "p-1"
        assert payload.items[0].title == "Mouse"
        assert payload.within_budget is True

    def test_no_candidates_returns_none(self):
        assert bundle_payload_from_candidates([]) is None


class TestEscalationDecision:
    def test_build_decision(self):
        decision = build_escalation_decision(
            should_escalate=True,
            reason="Customer explicitly requested a human agent.",
            confidence=0.95,
            priority="p3",
            signals=["explicit_human_request"],
            summary="Customer explicitly requested to speak to a human agent.",
            category="general",
            ticket_id="t-1",
            assigned_to="support",
        )
        assert isinstance(decision, EscalationDecision)
        assert decision.should_escalate is True
        assert decision.reason == "Customer explicitly requested a human agent."
        assert decision.confidence == 0.95
        assert decision.priority == "p3"
        assert decision.signals == ["explicit_human_request"]
        assert decision.summary is not None
        assert decision.ticket_id == "t-1"
        assert decision.assigned_to == "support"

    def test_default_not_escalated(self):
        decision = build_escalation_decision()
        assert decision.should_escalate is False
        assert decision.confidence == 0.0
        assert decision.signals == []
        assert decision.ticket_id is None

    def test_confidence_is_clamped(self):
        decision = build_escalation_decision(should_escalate=True, confidence=1.7)
        assert decision.confidence == 1.0
        decision = build_escalation_decision(should_escalate=True, confidence=-0.3)
        assert decision.confidence == 0.0


class TestTurnTraceAndResponse:
    def test_conversation_turn_trace_defaults(self):
        trace = ConversationTurnTrace(message_id="m-1")
        assert trace.request_id == ""
        assert trace.history_count == 0
        assert trace.steps == []

    def test_ai_turn_contract_requires_message_and_response(self):
        contract = AITurnContract(message_id="m-1", response="hello")
        assert contract.response_type == "text"
        assert contract.products == []
        assert contract.bundle is None
