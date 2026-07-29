import logging

from docx import Document

from app.infrastructure.knowledge.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class DOCXExtractor(BaseExtractor):
    async def extract(self, file_path: str) -> str:
        try:
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs]
            text = "\n".join(paragraphs)
            logger.debug("Extracted %d characters from DOCX '%s'", len(text), file_path)
            return text
        except Exception:
            logger.error("Failed to extract DOCX text from '%s'", file_path, exc_info=True)
            raise

    def supported_mime_types(self) -> list[str]:
        return [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

    def supported_extensions(self) -> list[str]:
        return [".docx"]
