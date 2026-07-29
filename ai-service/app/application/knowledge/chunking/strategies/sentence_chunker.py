import logging
import re

from app.application.knowledge.chunking.config import ChunkingConfig
from app.application.knowledge.chunking.strategies.base import BaseChunker

logger = logging.getLogger(__name__)


class SentenceChunker(BaseChunker):
    SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")

    @property
    def strategy_name(self) -> str:
        return "sentence"

    def chunk(self, text: str, config: ChunkingConfig) -> list[str]:
        sentences = self.SENTENCE_PATTERN.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return []

        chunks = []
        current = ""
        for sentence in sentences:
            candidate = (current + " " + sentence) if current else sentence
            if len(candidate) <= config.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(sentence) <= config.chunk_size:
                    current = sentence
                else:
                    for start in range(0, len(sentence), config.chunk_size - config.overlap):
                        seg = sentence[start:start + config.chunk_size]
                        if seg:
                            chunks.append(seg)
                    current = ""
        if current:
            chunks.append(current)

        if config.overlap > 0 and len(chunks) > 1:
            chunks = self._apply_sentence_overlap(chunks, config.overlap)
        return chunks

    def _apply_sentence_overlap(self, chunks: list[str], overlap: int) -> list[str]:
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = result[-1]
            tail = prev[-overlap:] if len(prev) >= overlap else prev
            result.append(tail + " " + chunks[i] if tail else chunks[i])
        return result
