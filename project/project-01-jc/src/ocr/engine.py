"""OcrEngine - generic PaddleOCR wrapper.

Provides a card-type-agnostic interface (recognize one image -> OcrResult)
so business logic never touches PaddleOCR directly. See spec-01 §3.2/§3.3.

Key behaviours:
- Lazy load: the PaddleOCR instance is created on first recognize() call.
- Module-level singleton via get_engine().
- Thread-safe initialization (recognition itself is expected to be
  called serially from the batch worker thread).
- Never raises for bad input: returns OcrResult.error instead.
"""
import os
import time
from threading import Lock

# MUST be set before importing paddle/paddleocr - see spec-01 §3.3.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

import src.config as cfg  # noqa: E402

from src.ocr.models import OcrResult, OcrWord  # noqa: E402


class OcrEngine:
    def __init__(self, config: dict | None = None) -> None:
        """Construct with config only; the model is NOT loaded here."""
        self._config = config or {}
        self._ocr = None
        self._lock = Lock()

    # ---- public API ----

    def recognize(self, image_path: str) -> OcrResult:
        """Recognize text in the image at image_path.

        Lazy-loads the engine on first call. Returns an OcrResult; on any
        failure `error` is set and no exception propagates.
        """
        ocr = self._get_ocr()
        start = time.perf_counter()
        try:
            result = ocr.predict(image_path)
            words = self._parse(result)
            elapse_ms = (time.perf_counter() - start) * 1000.0
            return OcrResult(words=words, image_path=image_path, elapse_ms=elapse_ms)
        except Exception as exc:  # noqa: BLE001 - surface any engine failure
            return OcrResult(
                words=[],
                image_path=image_path,
                elapse_ms=0.0,
                error=str(exc),
            )

    def warmup(self) -> None:
        """Force the model to load on the calling (UI) thread.

        PaddleOCR init stalls when it first happens off the main thread
        (measured >=60s), so the UI warms the engine up before any batch runs;
        worker threads then only ever call predict(). Idempotent.
        """
        self._get_ocr()

    def close(self) -> None:
        """Release the model instance; next recognize() reloads it."""
        self._ocr = None

    # ---- internals ----

    def _get_ocr(self):
        if self._ocr is None:
            with self._lock:
                if self._ocr is None:
                    from paddleocr import PaddleOCR

                    # Orientation + unwarping are handled by our own
                    # preprocess pipeline (stage 2); disable them for speed.
                    # Use the tiny model variant to meet the ≤1.5s CPU budget.
                    self._ocr = PaddleOCR(
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        use_textline_orientation=False,
                        lang=self._config.get("lang", cfg.OCR_LANG),
                        text_detection_model_name=self._config.get(
                            "det_model", cfg.OCR_DET_MODEL
                        ),
                        text_recognition_model_name=self._config.get(
                            "rec_model", cfg.OCR_REC_MODEL
                        ),
                    )
        return self._ocr

    @staticmethod
    def _parse(result) -> list[OcrWord]:
        """Map PaddleOCR predict() output to OcrWord list."""
        words: list[OcrWord] = []
        if not result:
            return words
        res = result[0].json.get("res", result[0].json)
        texts = res.get("rec_texts") or res.get("det_texts") or []
        scores = res.get("rec_scores") or []
        boxes = res.get("rec_polys") or res.get("det_polys") or []
        for i, text in enumerate(texts):
            conf = float(scores[i]) if i < len(scores) else 0.0
            box = boxes[i] if i < len(boxes) else None
            words.append(OcrWord(text=text, confidence=conf, box=box))
        return words


_engine_singleton: OcrEngine | None = None


def get_engine() -> OcrEngine:
    """Return the global OcrEngine singleton (avoids reloading the model)."""
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = OcrEngine()
    return _engine_singleton
