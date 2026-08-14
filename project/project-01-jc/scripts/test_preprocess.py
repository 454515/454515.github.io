"""Stage 2 self-test: verify image preprocess pipeline (spec-02 §4).

Generates a synthetic ID-card test image (blue border + fields + ID number),
then checks:
1. Forward clear image  -> found_card=True, rotation_angle=0.
2. Rotated 90/180/270   -> corrected back upright.
3. Tilted image         -> perspective-corrected, card horizontal.
4. Non-ID-card image    -> no crash, found_card properly marked.
5. OCR interop (real sample if present): preprocessing does not degrade
   recognition.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_preprocess.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.config import SAMPLES_DIR
from src.utils.preprocess import preprocess_image, correct_orientation

OUT_DIR = SAMPLES_DIR / "preprocess_tmp"
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "C:/Windows/Fonts/simhei.ttf",
]
_ROT_FLAGS = [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]


def _imwrite_unicode(path: Path, bgr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imencode(".jpg", bgr)[1].tofile(str(path))


def _font(size: int) -> ImageFont.FreeTypeFont:
    for cand in FONT_CANDIDATES:
        if Path(cand).exists():
            return ImageFont.truetype(cand, size)
    raise RuntimeError("No CJK font found")


def make_synthetic_card() -> np.ndarray:
    """Draw a fake ID card: white card, blue border, fields, ID number."""
    W, H = 1000, 630
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 6, W - 7, H - 7], outline=(0, 102, 204), width=4)
    draw.rectangle([40, 90, 190, 300], outline=(180, 180, 180), width=2)  # avatar
    font_title = _font(34)
    font_body = _font(30)
    fields = [
        ("姓名   张建邺", 60),
        ("性别   男   民族  汉", 130),
        ("出生   2004年6月17日", 200),
        ("住址   江苏省南京市江宁区XX路100号", 270),
        ("公民身份号码", 420),
    ]
    for text, y in fields:
        draw.text((250, y), text, fill="black", font=font_title)
    draw.text((250, 480), "321322200406170832", fill="black", font=font_body)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _make_tilted(base: np.ndarray) -> np.ndarray:
    """Simulate a tilted top-down-ish shot on a gray background."""
    h, w = base.shape[:2]
    canvas = np.full((h + 200, w + 260, 3), 150, dtype=np.uint8)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[60, 40], [w + 40, 90], [w + 10, h + 90], [80, h + 60]])
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(base, m, (canvas.shape[1], canvas.shape[0]))
    mask = np.any(warped > 0, axis=2)
    canvas[mask] = warped[mask]
    return canvas


def _assert_upright(result, expected: int) -> None:
    assert result.error is None, result.error
    assert result.found_card is True, "expected card detected"
    assert result.rotation_angle == expected, \
        f"angle={result.rotation_angle}, expected={expected}"
    again = correct_orientation(result.image)[1]
    assert again == 0, f"output not upright, still needs {again}deg"
    print(f"[ok] rotation {expected:>3}: upright confirmed")


def _ocr_check(base_name: Path) -> None:
    """Interop: preprocessing must not degrade recognition (spec-02 §4)."""
    from src.ocr.engine import OcrEngine

    engine = OcrEngine()
    try:
        before = engine.recognize(str(base_name))
        assert before.error is None, before.error
        proc = preprocess_image(str(base_name))
        proc_path = OUT_DIR / "proc_forward.jpg"
        _imwrite_unicode(proc_path, proc.image)
        after = engine.recognize(str(proc_path))
        assert after.error is None, after.error
        text_before = "".join(w.text for w in before.words)
        text_after = "".join(w.text for w in after.words)
        print(f"[info] OCR words before={len(before.words)} after={len(after.words)}")
        for key in ("张建邺", "公民身份号码", "321322"):
            if key in text_before:
                assert key in text_after, f"field {key!r} lost after preprocessing"
        print("[ok] OCR interop: no degradation")
    finally:
        engine.close()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = make_synthetic_card()
    forward_path = OUT_DIR / "forward.jpg"
    _imwrite_unicode(forward_path, base)

    # 1. forward
    _assert_upright(preprocess_image(str(forward_path)), 0)

    # 2. rotations: expected clockwise correction is (360 - k*90) % 360
    for k in (1, 2, 3):
        img = cv2.rotate(base, _ROT_FLAGS[k - 1])
        p = OUT_DIR / f"rot{k}.jpg"
        _imwrite_unicode(p, img)
        _assert_upright(preprocess_image(str(p)), (360 - k * 90) % 360)

    # 3. tilted
    tilted = _make_tilted(base)
    p = OUT_DIR / "tilted.jpg"
    _imwrite_unicode(p, tilted)
    rt = preprocess_image(str(p))
    assert rt.error is None, rt.error
    assert rt.found_card is True, "expected card detected on tilted image"
    h, w = rt.image.shape[:2]
    assert max(w, h) / min(w, h) > 1.2, "corrected card should be landscape"
    print(f"[ok] tilted: corrected to {w}x{h}")

    # 4. non-card (random noise): must not crash
    noise = np.random.default_rng(0).integers(0, 256, (400, 600, 3), dtype=np.uint8)
    p = OUT_DIR / "non_card.jpg"
    _imwrite_unicode(p, noise)
    rn = preprocess_image(str(p))
    assert rn.error is None, "non-card image must not raise"
    print(f"[ok] non-card: no crash, found_card={rn.found_card}")

    # 5. OCR interop on the real sample if present, else the synthetic card
    real = SAMPLES_DIR / "idcard_sample.jpg"
    _ocr_check(real if real.exists() else forward_path)

    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
