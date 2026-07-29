from abc import ABC, abstractmethod

from app.domain.prompt.entities.prompt import Prompt
from app.shared.kernel.repository import AsyncRepository


class PromptRepository(AsyncRepository[Prompt, str], ABC):
    @abstractmethod
    async def find_by_key(self, key: str) -> Prompt | None: ...

    @abstractmethod
    async def find_by_keys(self, keys: list[str]) -> list[Prompt]: ...

    @abstractmethod
    async def find_by_tags(self, tags: list[str], limit: int = 100, skip: int = 0) -> list[Prompt]: ...

    @abstractmethod
    async def search(
        self,
        query: str = "",
        type_filter: str | None = None,
        tag_filter: list[str] | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> tuple[list[Prompt], int]: ...

    @abstractmethod
    async def upsert_by_key(self, entity: Prompt) -> Prompt: ...
