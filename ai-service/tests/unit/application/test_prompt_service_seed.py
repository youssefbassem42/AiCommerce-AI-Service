from datetime import UTC, datetime

import pytest

from app.application.admin.services.prompt_service import PromptService
from app.domain.prompt.entities.prompt import Prompt
from app.infrastructure.prompts.seed import DEFAULT_PROMPTS

KEY = "coordinator.intent_classification_prompt"


def _prompt(key: str = KEY, version: int = 1, content: str = "old") -> Prompt:
    return Prompt(
        id=f"id-{key}",
        key=key,
        content=content,
        description="old desc",
        tags=["old"],
        version=version,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class FakePromptRepository:
    def __init__(self, prompts: list[Prompt]):
        self._by_key = {p.key: p for p in prompts}
        self.created: list[Prompt] = []
        self.updated: list[Prompt] = []

    async def find_by_key(self, key: str) -> Prompt | None:
        return self._by_key.get(key)

    async def create(self, entity: Prompt) -> Prompt:
        self._by_key[entity.key] = entity
        self.created.append(entity)
        return entity

    async def update(self, entity: Prompt) -> Prompt:
        self._by_key[entity.key] = entity
        self.updated.append(entity)
        return entity

    async def delete(self, entity_id: str) -> bool:
        return True


@pytest.mark.asyncio
async def test_seed_defaults_refreshes_drifted_pristine_prompt():
    repo = FakePromptRepository([_prompt(version=1, content="legacy default content")])
    service = PromptService(repository=repo)

    count = await service.seed_defaults()

    assert count >= 1
    refreshed = repo.updated
    assert any(p.key == KEY for p in refreshed)
    stored = repo._by_key[KEY]
    assert stored.content == DEFAULT_PROMPTS[KEY]["content"]
    assert stored.version == 1


@pytest.mark.asyncio
async def test_seed_defaults_never_overwrites_admin_customized_prompt():
    repo = FakePromptRepository([_prompt(version=3, content="admin customized content")])
    service = PromptService(repository=repo)

    await service.seed_defaults()

    assert repo._by_key[KEY].content == "admin customized content"
    assert not any(p.key == KEY for p in repo.updated)


@pytest.mark.asyncio
async def test_seed_defaults_creates_missing_prompts():
    repo = FakePromptRepository([])
    service = PromptService(repository=repo)

    count = await service.seed_defaults()

    assert count == len(DEFAULT_PROMPTS)
    assert len(repo.created) == len(DEFAULT_PROMPTS)
    assert repo._by_key[KEY].content == DEFAULT_PROMPTS[KEY]["content"]
