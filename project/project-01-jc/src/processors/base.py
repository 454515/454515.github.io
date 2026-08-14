"""BaseProcessor - abstract interface for card-type field extraction.

Subclasses map an OcrResult (OCR words) into a structured CardResult.
Pure function of the words: no UI, no image access, no OCR invocation.
"""
from abc import ABC, abstractmethod

from src.ocr.models import OcrResult
from src.processors.models import CardResult


class BaseProcessor(ABC):
    """Extract structured fields from OCR words for one card type."""

    card_type: str = ""

    @abstractmethod
    def process(self, ocr_result: OcrResult) -> CardResult:
        """Map OCR words to a structured CardResult."""
        raise NotImplementedError
