"""Stage 1 self-test: verify OcrEngine interface (spec-01 §4).

Checks:
1. Lazy load: model is NOT loaded before the first recognize() call.
2. Sample image: error is None and words is non-empty.
3. Damaged image: error is set, no exception propagates.
4. Print per-image elapsed time.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_ocr_engine.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ocr.engine import OcrEngine  # noqa: E402

SAMPLE = PROJECT_ROOT / "assets" / "samples" / "idcard_sample.jpg"
BAD_IMAGE = PROJECT_ROOT / "assets" / "samples" / "bad_image.jpg"


def main() -> int:
    engine = OcrEngine()

    # 1. Lazy load
    assert engine._ocr is None, "model must not be loaded before first recognize()"
    print("[ok] lazy load: model not initialized before recognize()")

    # 2. Sample image
    result = engine.recognize(str(SAMPLE))
    assert result.error is None, f"unexpected error: {result.error}"
    assert len(result.words) > 0, "no words recognized on sample image"
    print(f"[ok] recognized {len(result.words)} words, elapse={result.elapse_ms:.0f}ms")
    for word in result.words:
        print(f"  {word.text!r} (conf={word.confidence:.3f})")

    # 3. Damaged image
    BAD_IMAGE.write_bytes(b"this is definitely not an image file")
    try:
        result2 = engine.recognize(str(BAD_IMAGE))
    finally:
        BAD_IMAGE.unlink(missing_ok=True)
    assert result2.error is not None, "expected error for damaged image"
    print(f"[ok] damaged image handled, error={result2.error[:60]!r}")

    engine.close()
    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
