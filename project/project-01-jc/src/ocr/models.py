"""OCR engine data models.

Unified, card-type-agnostic result types so the layers above never touch
PaddleOCR/PaddleX types directly. See spec-01 §3.1.
"""
from dataclasses import dataclass, field


@dataclass
class OcrWord:
    """A single recognized text block."""

    text: str                      # recognized text
    confidence: float              # confidence 0~1
    box: list | None               # quad [[x,y],[x,y],[x,y],[x,y]] or None
    # (mapped from PaddleOCR rec_texts/rec_scores/rec_polys)


@dataclass
class OcrResult:
    """Result of recognizing one image."""

    words: list[OcrWord] = field(default_factory=list)
    image_path: str = ""           # source image path
    elapse_ms: float = 0.0         # recognition elapsed time (ms)
    error: str | None = None       # None = success, otherwise error description
