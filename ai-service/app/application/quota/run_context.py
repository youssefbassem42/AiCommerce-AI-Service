"""Per-request quota run state (contextvar).

A single widget chat turn may involve several LLM calls (orchestrated
coordinator+agents). The enforcer needs (a) the store's plan during execution
and (b) the aggregated actual usage of the whole turn. FailoverProvider reads
and records into the contextvar set by the enforcement entry point.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

from app.application.dto.ai_dto import UsageDTO
from app.domain.analytics.entities.plan_policy import PlanPolicy


@dataclass
class QuotaRunState:
    store_id: str | None = None
    plan: PlanPolicy | None = None
    usage_records: list[dict] = field(default_factory=list)
    llm_calls: int = 0

    def record(self, provider: str, model: str, usage: UsageDTO) -> None:
        self.llm_calls += 1
        self.usage_records.append(
            {
                "provider": provider,
                "model": model,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost": usage.cost,
            }
        )

    def totals(self) -> dict:
        prompt = sum(r["prompt_tokens"] for r in self.usage_records)
        completion = sum(r["completion_tokens"] for r in self.usage_records)
        total = sum(r["total_tokens"] for r in self.usage_records)
        cost = sum(r["cost"] for r in self.usage_records)
        providers = list({r["provider"] for r in self.usage_records})
        models = list({r["model"] for r in self.usage_records})
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "cost": cost,
            "providers": providers,
            "models": models,
            "llm_calls": self.llm_calls,
        }


_quota_run: ContextVar[QuotaRunState | None] = ContextVar("quota_run", default=None)


def set_quota_run(state: QuotaRunState | None) -> QuotaRunState | None:
    token = _quota_run.set(state)
    state._token = token  # type: ignore[attr-defined]
    return state


def get_quota_run() -> QuotaRunState | None:
    return _quota_run.get()


def reset_quota_run() -> None:
    state = _quota_run.get()
    if state is not None and hasattr(state, "_token"):
        _quota_run.reset(state._token)  # type: ignore[attr-defined]
    _quota_run.set(None)
