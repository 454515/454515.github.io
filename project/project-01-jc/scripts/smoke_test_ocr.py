"""Stage 0 smoke test: verify the PaddleOCR engine works end-to-end.

If no real sample image exists yet, generates a synthetic Chinese test image
(containing fake ID-card field text) with Pillow + the system Microsoft YaHei
font, then runs PaddleOCR on it and prints the detected text blocks.

Usage:
    .venv\\Scripts\\python.exe scripts\\smoke_test_ocr.py
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# MUST be set before importing paddle/paddleocr:
# paddlepaddle 3.3.1 on Windows hits an oneDNN instruction bug
# (ConvertPirAttribute2RuntimeAttribute not support) when paddlex enables
# mkldnn by default. Disable it here so the smoke test is reproducible
# regardless of the outer environment. Stage 1's OcrEngine must do the same.
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")

from src.config import SAMPLES_DIR  # noqa: E402

SAMPLE_PATH = SAMPLES_DIR / "idcard_sample.jpg"
YAHEI_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",   # Microsoft YaHei
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",  # SimHei fallback
]


def _ensure_sample_image() -> Path:
    """Return an existing sample image; generate a synthetic one if absent."""
    if SAMPLE_PATH.exists():
        return SAMPLE_PATH
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for candidate in YAHEI_CANDIDATES:
        if Path(candidate).exists():
            font = ImageFont.truetype(candidate, 36)
            break
    if font is None:
        raise RuntimeError("No CJK font found to render the synthetic sample image")

    img = Image.new("RGB", (800, 460), "white")
    draw = ImageDraw.Draw(img)
    # Fake ID-card layout so OCR exercises real Chinese text.
    rows = [
        "姓名   张  三",
        "性别   男   民族 汉",
        "公民身份号码",
        "110101 1990 01 01 1234",
    ]
    y = 60
    for row in rows:
        draw.text((60, y), row, fill="black", font=font)
        y += 80

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    img.save(SAMPLE_PATH)
    print(f"[info] generated synthetic sample: {SAMPLE_PATH}")
    return SAMPLE_PATH


def main() -> int:
    image_path = _ensure_sample_image()
    print(f"[info] recognizing: {image_path}")

    from paddleocr import PaddleOCR

    # paddleocr 3.x API: use_doc_orientation_classify / use_doc_unwarping /
    # use_textline_orientation replace the removed use_angle_cls.
    # Orientation + warping are handled by our own preprocess pipeline (stage 2),
    # so we disable them here to keep recognition fast (≤1.5s target).
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang="ch",
    )
    result = ocr.predict(str(image_path))

    if not result:
        print("[fail] no result returned")
        return 1

    data = result[0].json
    res = data.get("res", data)
    texts = res.get("rec_texts") or res.get("det_texts") or []
    scores = res.get("rec_scores") or []

    if not texts:
        print("[fail] no text block detected")
        return 1

    print(f"[ok] detected {len(texts)} text block(s); first 3:")
    for i, text in enumerate(texts[:3]):
        conf = scores[i] if i < len(scores) else 0.0
        print(f"  {i + 1}. {text!r} (conf={float(conf):.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
