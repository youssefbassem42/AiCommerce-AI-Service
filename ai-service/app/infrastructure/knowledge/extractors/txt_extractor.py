import logging

import chardet

from app.infrastructure.knowledge.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class TXTExtractor(BaseExtractor):
    async def extract(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            detected = chardet.detect(raw)
            encoding = detected.get("encoding") or "utf-8"
            text = raw.decode(encoding, errors="replace")
            logger.debug(
                "Extracted %d characters from TXT '%s' (encoding: %s)",
                len(text), file_path, encoding,
            )
            return text
        except Exception:
            logger.error("Failed to extract TXT text from '%s'", file_path, exc_info=True)
            raise

    def supported_mime_types(self) -> list[str]:
        return ["text/plain"]

    def supported_extensions(self) -> list[str]:
        return [".txt"]
