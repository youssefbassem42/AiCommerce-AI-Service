import logging

from app.application.knowledge.chunking.config import ChunkingConfig
from app.application.knowledge.chunking.strategies.base import BaseChunker

logger = logging.getLogger(__name__)


class RecursiveCharacterChunker(BaseChunker):
    SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    @property
    def strategy_name(self) -> str:
        return "recursive"

    def chunk(self, text: str, config: ChunkingConfig) -> list[str]:
        return self._chunk_recursive(text, config.chunk_size, config.overlap)

    def _chunk_recursive(self, text: str, chunk_size: int, overlap: int, separators: list[str] | None = None) -> list[str]:
        if separators is None:
            separators = list(self.SEPARATORS)

        if len(text) <= chunk_size:
            return [text] if text else []

        for sep in separators:
            if sep == "":
                chunks = []
                start = 0
                while start < len(text):
                    end = min(start + chunk_size, len(text))
                    chunks.append(text[start:end])
                    start = end - overlap if end < len(text) else end
                return chunks

            if sep in text:
                parts = text.split(sep)
                chunks = []
                current = ""
                for part in parts:
                    candidate = (current + sep + part) if current else part
                    if len(candidate) <= chunk_size:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        if len(part) <= chunk_size:
                            current = part
                        else:
                            sub = self._chunk_recursive(part, chunk_size, overlap, separators[separators.index(sep) + 1:])
                            chunks.extend(sub)
                            current = ""
                if current:
                    chunks.append(current)

                if overlap > 0 and len(chunks) > 1:
                    chunks = self._apply_overlap(chunks, overlap, sep)
                return chunks

        return [text]

    def _apply_overlap(self, chunks: list[str], overlap: int, separator: str) -> list[str]:
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = result[-1]
            tail = prev[-overlap:] if len(prev) >= overlap else prev
            result.append(tail + separator + chunks[i] if tail else chunks[i])
        return result
