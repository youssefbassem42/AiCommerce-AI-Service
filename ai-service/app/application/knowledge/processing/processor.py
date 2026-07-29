import logging
from datetime import UTC, datetime

import tiktoken
from langdetect import DetectorFactory, LangDetectException, detect_langs

from app.application.knowledge.processing.pipeline import ProcessingPipeline
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.domain.knowledge.value_objects import ProcessingStats
from app.infrastructure.knowledge.extractors import ExtractorFactory

DetectorFactory.seed = 0

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(
        self,
        repository: KnowledgeRepository,
        extractor_factory: ExtractorFactory | None = None,
        pipeline: ProcessingPipeline | None = None,
    ):
        self.repository = repository
        self.extractor_factory = extractor_factory or ExtractorFactory()
        self.pipeline = pipeline or ProcessingPipeline()
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    async def process(
        self,
        document: KnowledgeDocument,
        file_path: str,
        mime_type: str | None = None,
    ) -> KnowledgeDocument:
        document.status = "processing"
        document.updated_at = datetime.now(UTC)
        await self.repository.update(document)

        try:
            raw_text = await self.extractor_factory.extract(file_path, mime_type)
            clean_text = self.pipeline.process(raw_text)
            stats = self._compute_stats(clean_text)
            detected = self._detect_language(clean_text)

            document.processed_text = clean_text
            document.page_count = stats.page_count
            document.word_count = stats.word_count
            document.char_count = stats.char_count
            document.estimated_tokens = stats.estimated_tokens
            document.language = detected or document.language
            document.metadata.attributes.update({
                "detected_language": detected or document.language,
                "processing_timestamp": datetime.now(UTC).isoformat(),
                "line_count": stats.line_count,
            })
            document.status = "active"
            document.updated_at = datetime.now(UTC)

            updated = await self.repository.update(document)
            logger.info(
                "Document '%s' processed: %d words, %d chars, %d tokens",
                document.id, stats.word_count, stats.char_count, stats.estimated_tokens,
            )
            return updated
        except Exception:
            document.status = "error"
            document.updated_at = datetime.now(UTC)
            await self.repository.update(document)
            logger.error("Failed to process document '%s'", document.id, exc_info=True)
            raise

    def _compute_stats(self, text: str) -> ProcessingStats:
        words = text.split()
        word_count = len(words)
        char_count = len(text)
        line_count = text.count("\n") + 1
        tokens = self._tokenizer.encode(text)
        return ProcessingStats(
            word_count=word_count,
            char_count=char_count,
            line_count=line_count,
            estimated_tokens=len(tokens),
        )

    def _detect_language(self, text: str) -> str | None:
        if not text.strip():
            return None
        try:
            detections = detect_langs(text[:2000])
            if detections:
                return detections[0].lang
        except LangDetectException:
            logger.debug("Language detection failed for text, falling back")
        return None
