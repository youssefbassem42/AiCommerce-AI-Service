import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    def normalize_unicode(self, text: str) -> str:
        return unicodedata.normalize("NFC", text)

    def remove_invalid_characters(self, text: str) -> str:
        allowed = {"\n", "\r", "\t"}
        return "".join(ch for ch in text if ch in allowed or unicodedata.category(ch) not in {"Cc", "Cf"} or ch == "\u200b")

    def remove_html(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        return text

    def normalize_whitespace(self, text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text

    def process(self, raw_text: str) -> str:
        text = self.normalize_unicode(raw_text)
        text = self.remove_invalid_characters(text)
        text = self.remove_html(text)
        text = self.normalize_whitespace(text)
        return text
