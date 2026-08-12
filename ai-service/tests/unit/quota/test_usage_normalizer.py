from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.application.quota.usage_normalizer import UsageNormalizer


def make_response(usage: UsageDTO | None = None, content: str = "hello world"):
    return ChatResponse(
        id="r1",
        message=MessageDTO(role="assistant", content=content),
        usage=usage,
        model="gpt-4o-mini",
        provider="openai",
        latency_ms=1.0,
    )


class TestUsageNormalization:
    def test_total_is_prompt_plus_completion(self):
        normalized = UsageNormalizer.normalize(
            make_response(usage=UsageDTO(prompt_tokens=100, completion_tokens=50, total_tokens=150))
        )
        assert normalized.total_tokens == 150
        assert normalized.prompt_tokens == 100
        assert normalized.completion_tokens == 50

    def test_missing_total_is_derived(self):
        normalized = UsageNormalizer.normalize(
            make_response(usage=UsageDTO(prompt_tokens=100, completion_tokens=50, total_tokens=0))
        )
        assert normalized.total_tokens == 150

    def test_only_total_reported_keeps_invariant(self):
        normalized = UsageNormalizer.normalize(
            make_response(usage=UsageDTO(prompt_tokens=0, completion_tokens=0, total_tokens=777))
        )
        assert normalized.total_tokens == 777

    def test_provider_actual_usage_wins_over_estimate(self):
        normalized = UsageNormalizer.normalize(
            make_response(usage=UsageDTO(prompt_tokens=5, completion_tokens=5, total_tokens=10), content="x" * 1000)
        )
        assert normalized.total_tokens == 10

    def test_no_usage_falls_back_to_estimation(self):
        normalized = UsageNormalizer.normalize(make_response(usage=UsageDTO(), content="hello world"))
        assert normalized.total_tokens > 0

    def test_estimate_from_text_is_completion_only(self):
        estimated = UsageNormalizer.estimate_from_text("hello world", "gpt-4o-mini")
        assert estimated.total_tokens > 0
        assert estimated.prompt_tokens == 0
        assert estimated.completion_tokens == estimated.total_tokens

    def test_negative_values_are_clamped(self):
        normalized = UsageNormalizer.normalize(
            make_response(usage=UsageDTO(prompt_tokens=-5, completion_tokens=-3, total_tokens=-100))
        )
        assert normalized.prompt_tokens >= 0
        assert normalized.completion_tokens >= 0
        assert normalized.total_tokens >= 0


class TestBudgetEstimation:
    def test_budget_respects_context_ceiling(self):
        messages = [MessageDTO(role="user", content="hello")]
        budget = UsageNormalizer.estimate_budget(messages, max_output_tokens=1024, model="gpt-4o-mini")
        assert 1 <= budget <= 8192

    def test_budget_never_zero(self):
        assert UsageNormalizer.estimate_budget([], max_output_tokens=0, model="gpt-4o-mini") >= 1
