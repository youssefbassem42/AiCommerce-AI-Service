"""Centralized token usage normalization (spec §12-13, §40).

Providers already normalize into ``UsageDTO`` (prompt/completion/total/cost)
via their adapters; this module guarantees the invariants used by the quota
engine and runtime logging so every AI route shares one calculation path:

- ``total_tokens = prompt_tokens + completion_tokens``
- actual provider usage wins; estimation is only a fallback for providers that
  report no usage (and for pre-flight budget sizing).
"""

from __future__ import annotations

from app.application.dto.ai_dto import ChatResponse, UsageDTO
from app.core.model_registry import ModelRegistry
from app.utils.token_utils import calculate_cost, calculate_tokens


class UsageNormalizer:
    """Normalizes provider usage into a canonical ``UsageDTO``."""

    @staticmethod
    def normalize(response: ChatResponse) -> UsageDTO:
        """Canonicalize the usage reported for a completed chat response."""
        usage = response.usage or UsageDTO()
        prompt = max(0, int(usage.prompt_tokens or 0))
        completion = max(0, int(usage.completion_tokens or 0))
        total = max(0, int(usage.total_tokens or 0))

        if total == 0 and (prompt or completion):
            total = prompt + completion
        if prompt == 0 and total:
            # Provider reported only a total — keep the invariant exact.
            prompt = total - completion if completion <= total else 0

        # Fallback estimation only when the provider reported nothing.
        if total == 0:
            text = response.message.content
            if isinstance(text, list):
                text = " ".join(str(part) for part in text)
            prompt = calculate_tokens(str(text), response.model)
            completion = 0
            total = prompt + completion

        cost = float(usage.cost or 0.0)
        if not cost:
            cost = calculate_cost(prompt, completion, response.model)

        return UsageDTO(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cost=cost,
        )

    @staticmethod
    def normalize_usage(usage: UsageDTO) -> UsageDTO:
        """Canonicalize a provider-reported ``UsageDTO`` (spec §12-13)."""
        prompt = max(0, int(usage.prompt_tokens or 0))
        completion = max(0, int(usage.completion_tokens or 0))
        total = max(0, int(usage.total_tokens or 0))
        if total == 0 and (prompt or completion):
            total = prompt + completion
        return UsageDTO(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cost=float(usage.cost or 0.0),
        )

    @staticmethod
    def estimate_from_text(text: str, model: str) -> UsageDTO:
        """Fallback estimation when a provider reported no usage (completion only)."""
        completion = max(0, calculate_tokens(str(text), model))
        return UsageDTO(
            prompt_tokens=0,
            completion_tokens=completion,
            total_tokens=completion,
            cost=calculate_cost(0, completion, model),
        )

    @staticmethod
    def estimate_budget(
        messages: list,
        max_output_tokens: int | None,
        model: str,
        headroom: float = 2.0,
    ) -> int:
        """Pre-flight budget estimate for a request (spec §7).

        Sizes the atomic reservation: estimated prompt tokens + capped output
        tokens, multiplied by ``headroom`` to absorb multi-call turns.
        """
        prompt_tokens = sum(
            calculate_tokens(m.content if isinstance(m.content, str) else str(m.content), model) for m in messages
        )
        ability = ModelRegistry.get_model_info(model)
        context_limit = ability.context_length if ability else 8192
        ceiling = max(1, int(context_limit * 0.8))
        output = min(int(max_output_tokens or 1024), 8192)
        return max(1, min(ceiling, int((prompt_tokens + output) * max(1.0, headroom))))
