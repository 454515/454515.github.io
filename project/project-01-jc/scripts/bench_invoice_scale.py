"""Benchmark: does downscaling a full-page invoice speed up OCR without
losing the 5 extracted fields? The real pipeline never shrinks
(preprocess_document only upscales), so a big scanned invoice feeds the full
resolution into PaddleOCR.

Usage:
    .venv\\Scripts\\python.exe scripts\\bench_invoice_scale.py [image]
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # noqa: E402

import src.config as cfg  # noqa: E402
from src.ocr.engine import OcrEngine  # noqa: E402
from src.processors.invoice import InvoiceProcessor  # noqa: E402
from src.utils.preprocess import _imread_unicode  # noqa: E402


def downscale(image, max_side: int) -> object:
    """Shrink (or upscale) so the long edge is <= max_side. Returns a copy."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image
    scale = max_side / longest
    return cv2.resize(image, (int(round(w * scale)), int(round(h * scale))),
                      interpolation=cv2.INTER_AREA)


def main() -> None:
    sample = sys.argv[1] if len(sys.argv) > 1 else \
        next(Path("发票样张").glob("*.jpg"))
    img = _imread_unicode(str(sample))
    if img is None:
        print("cannot decode", sample)
        return
    h, w = img.shape[:2]
    print(f"sample: {sample.name}  original {w}x{h}  "
          f"({w * h / 1e6:.2f}MP)")

    # Warm up model on this (main) thread once, then time hot runs.
    engine = OcrEngine()
    t0 = time.perf_counter()
    engine.warmup()
    print(f"cold model load: {time.perf_counter() - t0:.1f}s\n")

    processor = InvoiceProcessor()
    tmp = Path(tempfile.gettempdir()) / "bench_invoice.png"

    sizes = [max(h, w), 2000, 1600, 1300, 1100, 900]
    for max_side in sizes:
        pre = downscale(img, max_side)
        cv2.imencode(".png", pre)[1].tofile(str(tmp))
        # two hot runs, keep the best
        best, fields, missing = None, None, None
        for _ in range(2):
            t = time.perf_counter()
            ocr = engine.recognize(str(tmp))
            if ocr.error:
                print(f"  [{max_side:>5}] OCR error: {ocr.error}")
                break
            el = time.perf_counter() - t
            if best is None or el < best:
                best = el
                result = processor.process(ocr)
                fields, missing = result.fields, result.missing
        ok = "OK " if not missing else "MISS"
        print(f"[{max_side:>5}px] best {best * 1000:6.0f}ms  {ok}  "
              f"missing={missing or '-'}")
        print(f"           fields: " +
              " | ".join(f"{k}={v}" for k, v in fields.items()))
    tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
