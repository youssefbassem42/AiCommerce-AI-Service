"""Unit-test fixtures.

Unit tests run without a live MongoDB; prompts are served from the seeded
defaults so agent/tool behaviour stays deterministic (admin prompt CRUD and
PromptClient DB behaviour are covered by integration tests against real Mongo).
"""

import pytest

from app.infrastructure.prompts.seed import DEFAULT_PROMPTS


@pytest.fixture(autouse=True)
def prompt_defaults_fallback(monkeypatch):
    from app.infrastructure.prompts.client import PromptClient

    async def fake_get(self, key: str, default: str = "", use_fallback: bool = True) -> str:
        if key in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[key]["content"]
        return default

    async def fake_get_many(self, keys: list[str]) -> dict[str, str]:
        return {key: DEFAULT_PROMPTS[key]["content"] for key in keys if key in DEFAULT_PROMPTS}

    monkeypatch.setattr(PromptClient, "get", fake_get)
    monkeypatch.setattr(PromptClient, "get_many", fake_get_many)
