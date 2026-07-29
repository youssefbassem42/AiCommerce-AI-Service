import logging
from io import StringIO

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from app.infrastructure.knowledge.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class PDFExtractor(BaseExtractor):
    async def extract(self, file_path: str) -> str:
        output = StringIO()
        try:
            with open(file_path, "rb") as f:
                parser = PDFParser(f)
                doc = PDFDocument(parser)
                rsrcmgr = PDFResourceManager()
                device = TextConverter(rsrcmgr, output, laparams=LAParams())
                interpreter = PDFPageInterpreter(rsrcmgr, device)
                for page in PDFPage.create_pages(doc):
                    interpreter.process_page(page)
            text = output.getvalue()
            logger.debug("Extracted %d characters from PDF '%s'", len(text), file_path)
            return text
        except Exception:
            logger.error("Failed to extract PDF text from '%s'", file_path, exc_info=True)
            raise
        finally:
            output.close()

    def supported_mime_types(self) -> list[str]:
        return ["application/pdf"]

    def supported_extensions(self) -> list[str]:
        return [".pdf"]
