"""RecognitionService - background-thread batch recognition. spec-06 §3.

Runs the per-image pipeline (preprocess -> OCR -> field extraction) on a plain
daemon thread so the UI never blocks. Signals update the UI thread safely; a
failed image is skipped (fields empty) and counted.

Threading notes (measured, see progress.md key-decision 10):
- A QThread is avoided: PaddleOCR inference degrades badly on a QThread
  (>=15 s/image) while a plain python thread runs at ~1 s.
- The model is warmed up on the UI thread (MainWindow._warmup_engine) before
  any batch starts: a cold PaddleOCR init stalls (>60 s) off the main thread.
  This worker thread only ever calls predict() on the warmed-up engine.
"""
import os
import tempfile
import threading
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, Signal

from src.processors.models import CardResult


class RecognitionService(QObject):
    progress_updated = Signal(int, int)   # (current, total); current is 0-based
    image_started = Signal(str)           # current image filename
    result_ready = Signal(object, str)    # (CardResult, source path)
    batch_finished = Signal(int)          # failed count

    def __init__(self, engine, preprocess, processor) -> None:
        super().__init__()
        self._engine = engine
        self._preprocess = preprocess
        self._processor = processor
        self._images = []
        self._stop = False
        self._thread: threading.Thread | None = None

    def start_batch(self, images: list) -> None:
        self._images = list(images)
        self._stop = False
        self._thread = threading.Thread(target=self._run_batch, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop after the current image; no further images are taken."""
        self._stop = True

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_batch(self) -> None:
        total = len(self._images)
        failed = 0
        try:
            for i, img in enumerate(self._images):
                if self._stop:
                    break
                self.image_started.emit(img.filename)
                self.progress_updated.emit(i, total)
                try:
                    result = self._recognize_one(img.path)
                except Exception:
                    failed += 1
                    result = CardResult(card_type="idcard", fields={}, missing=[])
                self.result_ready.emit(result, img.path)
        except Exception:
            failed += 1  # keep the batch from dying silently
        self.batch_finished.emit(failed)

    # ---- internals ----

    def _recognize_one(self, path: str) -> CardResult:
        pre = self._preprocess(path)
        if pre is None or pre.image is None:
            raise ValueError("image decode failed")
        # OCR engine consumes a file path; preprocess output is an ndarray,
        # so write it to a temp PNG (unicode-safe via imencode + tofile) and
        # clean it up as soon as this image is done (PRD §3.3).
        tmp = Path(tempfile.gettempdir()) / f"ocr_{os.getpid()}_{id(self)}.png"
        try:
            cv2.imencode(".png", pre.image)[1].tofile(str(tmp))
            ocr = self._engine.recognize(str(tmp))
            if ocr.error:
                raise ValueError(ocr.error)
            return self._processor.process(ocr)
        finally:
            tmp.unlink(missing_ok=True)
