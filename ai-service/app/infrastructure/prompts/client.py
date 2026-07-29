import logging
from functools import lru_cache

from app.infrastructure.mongodb.repositories.prompt_repository import PromptRepository
from app.infrastructure.prompts.seed import DEFAULT_PROMPTS

logger = logging.getLogger(__name__)


class PromptClient:
    _instance = None

    def __init__(self):
        self._repo = PromptRepository()
        self._cache: dict[str, str] = {}

    @classmethod
    def instance(cls) -> "PromptClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get(self, key: str, default: str = "", use_fallback: bool = True) -> str:
        if key in self._cache:
            return self._cache[key]

        prompt = await self._repo.find_by_key(key)
        if prompt and prompt.is_active:
            self._cache[key] = prompt.content
            return prompt.content

        if use_fallback and key in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[key]["content"]

        return default

    async def get_many(self, keys: list[str]) -> dict[str, str]:
        prompts = await self._repo.find_by_keys(keys)
        result: dict[str, str] = {}
        loaded_keys = {p.key: p.content for p in prompts if p.is_active}
        for key in keys:
            if key in self._cache:
                result[key] = self._cache[key]
            elif key in loaded_keys:
                self._cache[key] = loaded_keys[key]
                result[key] = loaded_keys[key]
            elif key in DEFAULT_PROMPTS:
                result[key] = DEFAULT_PROMPTS[key]["content"]
            else:
                result[key] = ""
        return result

    def invalidate(self, key: str | None = None) -> None:
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()


@lru_cache(maxsize=1)
def get_prompt_client() -> PromptClient:
    return PromptClient.instance()
