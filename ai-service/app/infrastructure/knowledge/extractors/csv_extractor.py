import csv
import logging
from io import StringIO

import chardet

from app.infrastructure.knowledge.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class CSVExtractor(BaseExtractor):
    async def extract(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "utf-8"
            decoded = raw.decode(encoding, errors="replace")

            reader = csv.reader(StringIO(decoded))
            rows = []
            for row in reader:
                rows.append(" | ".join(row))
            text = "\n".join(rows) if rows else decoded
            logger.debug("Extracted %d characters from CSV '%s'", len(text), file_path)
            return text
        except Exception:
            logger.error("Failed to extract CSV text from '%s'", file_path, exc_info=True)
            raise

    def supported_mime_types(self) -> list[str]:
        return ["text/csv", "application/csv"]

    def supported_extensions(self) -> list[str]:
        return [".csv"]
