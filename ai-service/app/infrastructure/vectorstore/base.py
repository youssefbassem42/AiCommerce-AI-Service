from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VectorRecord:
    id: str
    vector: list[float]
    payload: dict[str, Any]


@dataclass
class SearchResult:
    id: str
    score: float
    payload: dict[str, Any]


@dataclass
class CollectionInfo:
    name: str
    vector_size: int
    distance: str
    points_count: int


class VectorStore(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 1536,
        distance: str = "Cosine",
    ) -> None:
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        pass

    @abstractmethod
    async def collection_exists(self, collection_name: str) -> bool:
        pass

    @abstractmethod
    async def list_collections(self) -> list[str]:
        pass

    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        pass

    @abstractmethod
    async def upsert(self, collection_name: str, points: list[VectorRecord]) -> int:
        pass

    @abstractmethod
    async def update(self, collection_name: str, points: list[VectorRecord]) -> int:
        pass

    @abstractmethod
    async def delete_by_id(self, collection_name: str, point_ids: list[str]) -> int:
        pass

    @abstractmethod
    async def delete_by_filter(
        self,
        collection_name: str,
        must: Optional[list[dict[str, Any]]] = None,
        must_not: Optional[list[dict[str, Any]]] = None,
    ) -> int:
        pass

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        vector: list[float],
        limit: int = 10,
        must: Optional[list[dict[str, Any]]] = None,
        must_not: Optional[list[dict[str, Any]]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchResult]:
        pass

    @abstractmethod
    async def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_type: str = "keyword",
    ) -> None:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass
