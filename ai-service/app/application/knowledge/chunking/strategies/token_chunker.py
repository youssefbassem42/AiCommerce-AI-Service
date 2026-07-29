import logging

import tiktoken

from app.application.knowledge.chunking.config import ChunkingConfig
from app.application.knowledge.chunking.strategies.base import BaseChunker

logger = logging.getLogger(__name__)


class TokenChunker(BaseChunker):
    def __init__(self, encoding_name: str = "cl100k_base"):
        self._tokenizer = tiktoken.get_encoding(encoding_name)

    @property
    def strategy_name(self) -> str:
        return "token"

    def chunk(self, text: str, config: ChunkingConfig) -> list[str]:
        tokens = self._tokenizer.encode(text)
        token_size = config.chunk_size
        token_overlap = config.overlap

        if not tokens:
            return []

        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + token_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self._tokenizer.decode(chunk_tokens)
            if chunk_text.strip():
                chunks.append(chunk_text)
            if end >= len(tokens):
                break
            start = end - token_overlap

        return chunks
