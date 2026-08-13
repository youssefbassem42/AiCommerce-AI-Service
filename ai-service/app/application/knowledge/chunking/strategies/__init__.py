from app.application.knowledge.chunking.strategies.base import BaseChunker
from app.application.knowledge.chunking.strategies.markdown_chunker import MarkdownChunker
from app.application.knowledge.chunking.strategies.recursive_character_chunker import (
    RecursiveCharacterChunker,
)
from app.application.knowledge.chunking.strategies.sentence_chunker import SentenceChunker
from app.application.knowledge.chunking.strategies.token_chunker import TokenChunker

STRATEGY_MAP: dict[str, type[BaseChunker]] = {
    "recursive": RecursiveCharacterChunker,
    "sentence": SentenceChunker,
    "markdown": MarkdownChunker,
    "token": TokenChunker,
}

STRATEGY_ALIASES: dict[str, str] = {
    "recursive_character": "recursive",
}


def get_chunker(strategy: str) -> BaseChunker:
    strategy = STRATEGY_ALIASES.get(strategy, strategy)
    cls = STRATEGY_MAP.get(strategy)
    if cls is None:
        msg = f"Unknown chunking strategy '{strategy}'. Available: {list(STRATEGY_MAP.keys())}"
        raise ValueError(msg)
    return cls()
