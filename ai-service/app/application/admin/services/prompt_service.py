import logging
from datetime import UTC, datetime

from app.domain.prompt.entities.prompt import Prompt
from app.infrastructure.mongodb.repositories.prompt_repository import PromptRepository
from app.infrastructure.prompts.client import get_prompt_client
from app.infrastructure.prompts.seed import DEFAULT_PROMPTS

logger = logging.getLogger(__name__)


def _invalidate_runtime_cache(key: str) -> None:
    """Propagate admin prompt edits to the runtime PromptClient cache."""
    try:
        get_prompt_client().invalidate(key)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to invalidate runtime prompt cache for '%s': %s", key, exc)


class PromptService:
    def __init__(self, repository: PromptRepository | None = None):
        self._repo = repository or PromptRepository()
        self._cache: dict[str, Prompt] = {}

    async def get_prompt(self, key: str) -> Prompt | None:
        if key in self._cache:
            return self._cache[key]
        prompt = await self._repo.find_by_key(key)
        if prompt and prompt.is_active:
            self._cache[key] = prompt
        return prompt

    async def get_content(self, key: str, default: str = "") -> str:
        prompt = await self.get_prompt(key)
        if prompt:
            return prompt.content
        fallback = DEFAULT_PROMPTS.get(key)
        if fallback is not None:
            return fallback["content"]
        return default

    async def list_prompts(
        self,
        query: str = "",
        type_filter: str | None = None,
        tag_filter: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Prompt], int]:
        skip = (page - 1) * page_size
        return await self._repo.search(
            query=query,
            type_filter=type_filter,
            tag_filter=tag_filter,
            limit=page_size,
            skip=skip,
        )

    async def create_prompt(
        self,
        key: str,
        type: str,
        content: str,
        description: str = "",
        tags: list[str] | None = None,
        variables: list[str] | None = None,
    ) -> Prompt:
        existing = await self._repo.find_by_key(key)
        if existing:
            raise ValueError(f"Prompt with key '{key}' already exists")

        latest = DEFAULT_PROMPTS.get(key)
        entity = Prompt(
            key=key,
            type=type,
            content=content,
            description=description or (latest["description"] if latest else ""),
            tags=tags or (latest["tags"] if latest else []),
            variables=variables or [],
            version=1,
            is_active=True,
        )
        self._cache.pop(key, None)
        _invalidate_runtime_cache(key)
        return await self._repo.create(entity)

    async def update_prompt(
        self,
        key: str,
        content: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        type: str | None = None,
        variables: list[str] | None = None,
        is_active: bool | None = None,
    ) -> Prompt:
        existing = await self._repo.find_by_key(key)
        if not existing:
            raise ValueError(f"Prompt with key '{key}' not found")

        if content is not None:
            existing.content = content
        if description is not None:
            existing.description = description
        if tags is not None:
            existing.tags = tags
        if type is not None:
            existing.type = type
        if variables is not None:
            existing.variables = variables
        if is_active is not None:
            existing.is_active = is_active

        existing.version += 1
        existing.updated_at = datetime.now(UTC)
        self._cache.pop(key, None)
        _invalidate_runtime_cache(key)
        return await self._repo.update(existing)

    async def delete_prompt(self, key: str) -> bool:
        existing = await self._repo.find_by_key(key)
        if not existing:
            return False
        self._cache.pop(key, None)
        _invalidate_runtime_cache(key)
        return await self._repo.delete(existing.id)

    async def restore_default(self, key: str) -> Prompt | None:
        default = DEFAULT_PROMPTS.get(key)
        if not default:
            return None

        existing = await self._repo.find_by_key(key)
        if existing:
            existing.content = default["content"]
            existing.description = default["description"]
            existing.tags = default["tags"]
            existing.type = default.get("type", "system")
            existing.variables = default.get("variables", [])
            existing.version += 1
            existing.updated_at = datetime.now(UTC)
            self._cache.pop(key, None)
            _invalidate_runtime_cache(key)
            return await self._repo.update(existing)

        entity = Prompt(
            key=key,
            type=default.get("type", "system"),
            content=default["content"],
            description=default["description"],
            tags=default["tags"],
            variables=default.get("variables", []),
            version=1,
            is_active=True,
        )
        self._cache.pop(key, None)
        _invalidate_runtime_cache(key)
        return await self._repo.create(entity)

    async def seed_defaults(self) -> int:
        count = 0
        for key, data in DEFAULT_PROMPTS.items():
            try:
                existing = await self._repo.find_by_key(key)
                if existing:
                    continue
                entity = Prompt(
                    key=key,
                    type=data.get("type", "system"),
                    content=data["content"],
                    description=data["description"],
                    tags=data["tags"],
                    variables=data.get("variables", []),
                    version=1,
                    is_active=True,
                )
                await self._repo.create(entity)
                count += 1
            except Exception as e:
                logger.warning("Failed to seed prompt '%s': %s", key, e)
        return count
