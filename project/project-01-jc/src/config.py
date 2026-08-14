# 检测识别 - 全局配置
"""Global configuration for the 检测识别 project.

All paths and constants that cross modules live here so that later stages
(OCR engine, processors, UI, packaging) share a single source of truth.
"""
import os
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    """App root.

    Dev: the repo checkout (src/config.py sits two levels down). Frozen
    (PyInstaller onefile): the directory that contains the exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()


def _get_models_dir() -> Path:
    """Directory PaddleX reads OCR models from.

    Frozen (PyInstaller):
    - onedir (new default): models/ ships alongside the exe, loaded directly.
    - onefile (legacy): models/ is bundled via --add-data and extracted to
      the ASCII-only _MEIPASS temp dir — a Chinese exe dir is fine because
      the models never live there.
    Dev: the project models/ dir (not used for loading; see the CACHE_HOME
    note below).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            # onefile mode: models extracted to a temp dir under _MEIPASS
            return Path(meipass) / "models"
        # onedir mode: models/ sits next to the exe
        return BASE_DIR / "models"
    return Path(__file__).resolve().parent.parent / "models"


# ---- Project root & directories ----
ASSETS_DIR = BASE_DIR / "assets"
SAMPLES_DIR = ASSETS_DIR / "samples"
MODELS_DIR = _get_models_dir()

# Offline model strategy (spec-07 §3.1, revised): models ship inside the onefile
# exe. Point PaddleX at them so OCR loads locally with zero download. Only set
# this when frozen: the project models/ dir sits under a Chinese path that
# Paddle's C++ runtime cannot read, so dev keeps the default ~/.paddlex cache.
if getattr(sys, "frozen", False) and MODELS_DIR.exists():
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(MODELS_DIR))

# ---- Supported image extensions (stage 5 import whitelist) ----
SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp")

# ---- Result table columns + field keys (single source of truth for the UI) ----
ID_CARD_COLUMNS = ["序号", "姓名", "性别", "身份证号"]
ID_CARD_FIELDS = ["name", "gender", "id_number"]
INVOICE_COLUMNS = ["序号", "姓名", "发票代码", "发票号码", "金额", "开票时间"]
INVOICE_FIELDS = ["name", "invoice_code", "invoice_no", "amount", "date"]

# ---- OCR engine config (stage 1) ----
OCR_LANG = "ch"
OCR_USE_ANGLE_CLS = True

# Model variants (paddlex registry). Default to v6_tiny: only variant meeting
# the ≤1.5s CPU budget without oneDNN (medium≈9.1s, small≈1.75s, tiny≈0.65s).
OCR_DET_MODEL = "PP-OCRv6_tiny_det"
OCR_REC_MODEL = "PP-OCRv6_tiny_rec"

# If a local model dir exists, OCR uses it; otherwise PaddleOCR auto-downloads.
OCR_MODEL_DIR = MODELS_DIR if MODELS_DIR.exists() else None

# ---- Image preprocess config (stage 2) ----
# PP-OCRv6_tiny misses small text (e.g. 男 in 性别男) at original size; upscale
# to ~1300px on the long side (~1.5x) so fields are detected reliably. Only
# upscale, never downscale (spec-02 §3.2).
PREPROCESS_MAX_SIDE = 1300

# Full-page documents (invoices): cap the long side instead of upscaling.
# Scanned/photographed pages feed OCR at full resolution (~3.7s on the sample);
# downscaling to 1300px cuts ~30% time with zero field loss (bench_invoice_scale).
# Images already within the cap are left untouched.
PREPROCESS_DOC_MAX_SIDE = 1300
