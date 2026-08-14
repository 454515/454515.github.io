"""Stage 1 perf bench: compare OCR model variants on the sample image.

Usage:
    .venv\\Scripts\\python.exe scripts\\bench_ocr.py <variant>

variant: v6_medium | v6_small | v6_tiny | v5_mobile
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from paddleocr import PaddleOCR  # noqa: E402

SAMPLE = str(PROJECT_ROOT / "assets" / "samples" / "idcard_sample.jpg")

VARIANTS = {
    "v6_medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
    "v6_small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
    "v6_tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec"),
    "v5_mobile": ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec"),
}


def bench(name: str, det: str, rec: str) -> None:
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang="ch",
        text_detection_model_name=det,
        text_recognition_model_name=rec,
    )
    ocr.predict(SAMPLE)  # warm up + model load
    times: list[float] = []
    last_words = 0
    for _ in range(3):
        t = time.perf_counter()
        res = ocr.predict(SAMPLE)
        times.append((time.perf_counter() - t) * 1000.0)
        r = res[0].json.get("res", res[0].json)
        last_words = len(r.get("rec_texts") or [])
    avg = sum(times) / len(times)
    detail = ", ".join(str(round(x)) for x in times)
    print(f"{name}: warm avg = {avg:.0f} ms ({detail}) | words={last_words}")


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else "v6_medium"
    if key not in VARIANTS:
        print(f"unknown variant {key!r}; choose from {sorted(VARIANTS)}")
        return 1
    det, rec = VARIANTS[key]
    bench(key, det, rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
