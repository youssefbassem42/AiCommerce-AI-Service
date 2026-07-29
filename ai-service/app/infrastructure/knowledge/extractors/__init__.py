import logging
import os

from app.infrastructure.knowledge.extractors.base import BaseExtractor
from app.infrastructure.knowledge.extractors.csv_extractor import CSVExtractor
from app.infrastructure.knowledge.extractors.docx_extractor import DOCXExtractor
from app.infrastructure.knowledge.extractors.pdf_extractor import PDFExtractor
from app.infrastructure.knowledge.extractors.txt_extractor import TXTExtractor

logger = logging.getLogger(__name__)


class ExtractorFactory:
    def __init__(self):
        self._extractors: dict[str, BaseExtractor] = {}
        self._register(PDFExtractor())
        self._register(DOCXExtractor())
        self._register(TXTExtractor())
        self._register(CSVExtractor())

    def _register(self, extractor: BaseExtractor) -> None:
        for ext in extractor.supported_extensions():
            self._extractors[ext.lower()] = extractor

    def get_extractor(self, file_path: str, mime_type: str | None = None) -> BaseExtractor:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self._extractors:
            return self._extractors[ext]
        if mime_type:
            for extractor in set(self._extractors.values()):
                if mime_type in extractor.supported_mime_types():
                    return extractor
        msg = f"No extractor available for '{file_path}' (ext: {ext}, mime: {mime_type})"
        raise ValueError(msg)

    async def extract(self, file_path: str, mime_type: str | None = None) -> str:
        extractor = self.get_extractor(file_path, mime_type)
        return await extractor.extract(file_path)
