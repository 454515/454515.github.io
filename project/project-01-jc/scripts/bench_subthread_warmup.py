# -*- coding: utf-8 -*-
"""Re-verify key-decision-11: does PaddleOCR init stall on a non-main thread
with a live QApplication in the CURRENT environment (paddle 3.3.1, PySide6,
onedir, Chinese-path-free repo)?

Scenarios tested:
  A. sub-thread does import paddle + import paddleocr + PaddleOCR(...)   [worst case]
  B. main thread pre-imports paddle/paddleocr, sub-thread creates PaddleOCR

If sub-thread init finishes in a few seconds, the UI can warm the model on a
background thread and stay fully responsive at startup. If it stalls, the
main-thread warmup (current behaviour) is unavoidable.
"""
import os
import sys
import time
import threading

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

STALL_AFTER = 15  # seconds
result = {}


def _make_ocr():
    from paddleocr import PaddleOCR

    return PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang="ch",
        text_detection_model_name="PP-OCRv6_tiny_det",
        text_recognition_model_name="PP-OCRv6_tiny_rec",
    )


def scenario_a():
    def worker():
        t0 = time.perf_counter()
        try:
            import paddle  # noqa: F401
            t1 = time.perf_counter()
            import paddleocr  # noqa: F401
            t2 = time.perf_counter()
            _make_ocr()
            t3 = time.perf_counter()
            result["a"] = ("ok", t1 - t0, t2 - t1, t3 - t2)
        except Exception as exc:  # noqa: BLE001
            result["a"] = ("err", str(exc))

    threading.Thread(target=worker, daemon=True).start()


def scenario_b():
    # Main thread pre-imports the heavy packages; sub-thread only instantiates.
    import paddle  # noqa: F401
    import paddleocr  # noqa: F401

    def worker():
        t0 = time.perf_counter()
        try:
            _make_ocr()
            result["b"] = ("ok", time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            result["b"] = ("err", str(exc))

    threading.Thread(target=worker, daemon=True).start()


def main() -> int:
    app = QApplication(sys.argv)
    t_start = time.perf_counter()
    scenario_a()
    scenario_b()

    def check() -> None:
        el = time.perf_counter() - t_start
        if "a" in result and "b" in result:
            print(f"elapsed={el:.1f}s")
            print(f"A(sub-thread import+create) = {result['a']}")
            print(f"B(main-import/sub-create) = {result['b']}")
            app.quit()
        elif el > STALL_AFTER:
            print(f"STALL: no result after {STALL_AFTER}s")
            print(f"A = {result.get('a')}")
            print(f"B = {result.get('b')}")
            app.quit()
        else:
            QTimer.singleShot(200, check)

    QTimer.singleShot(200, check)
    app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
