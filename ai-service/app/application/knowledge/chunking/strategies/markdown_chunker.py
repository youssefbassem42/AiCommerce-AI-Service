import logging
import re

from app.application.knowledge.chunking.config import ChunkingConfig
from app.application.knowledge.chunking.strategies.base import BaseChunker

logger = logging.getLogger(__name__)


class MarkdownChunker(BaseChunker):
    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    @property
    def strategy_name(self) -> str:
        return "markdown"

    def chunk(self, text: str, config: ChunkingConfig) -> list[str]:
        sections = self._split_by_headers(text)
        chunks = []
        for heading, body in sections:
            section_text = (heading + "\n" + body) if heading else body
            if len(section_text) <= config.chunk_size or not heading:
                if section_text.strip():
                    chunks.append(section_text.strip())
            else:
                sub_chunks = self._split_large_section(section_text, config)
                chunks.extend(sub_chunks)

        if config.overlap > 0 and len(chunks) > 1:
            chunks = self._apply_markdown_overlap(chunks, config.overlap)
        return chunks

    def _split_by_headers(self, text: str) -> list[tuple[str, str]]:
        matches = list(self.HEADER_PATTERN.finditer(text))
        sections = []
        for i, match in enumerate(matches):
            heading = match.group(0)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append((heading, body))
        if not matches:
            sections.append(("", text.strip()))
        return sections

    def _split_large_section(self, text: str, config: ChunkingConfig) -> list[str]:
        chunks = []
        for i in range(0, len(text), config.chunk_size - config.overlap):
            seg = text[i:i + config.chunk_size]
            if seg.strip():
                chunks.append(seg.strip())
        return chunks

    def _apply_markdown_overlap(self, chunks: list[str], overlap: int) -> list[str]:
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = result[-1]
            tail = prev[-overlap:] if len(prev) >= overlap else prev
            result.append(tail + "\n\n" + chunks[i] if tail else chunks[i])
        return result
