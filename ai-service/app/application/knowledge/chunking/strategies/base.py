from abc import ABC, abstractmethod

from app.application.knowledge.chunking.config import ChunkingConfig


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, text: str, config: ChunkingConfig) -> list[str]:
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        pass
