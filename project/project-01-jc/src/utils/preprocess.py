"""Image preprocess pipeline for OCR. See spec-02 §3.2/§3.3.

Pipeline order: size normalize -> orientation correct -> perspective correct
-> background removal. Every step degrades to pass-through on failure so OCR
always gets a chance to run (spec-02 §3.4).

Chinese-path safe: reading uses cv2.imdecode(np.fromfile(...)) because
cv2.imread cannot handle non-ASCII paths (key decision #5 in progress.md).
"""
import numpy as np
import cv2

import src.config as cfg

from src.utils.preprocess_models import PreprocessResult

# --- rotation helpers -----------------------------------------------------
# cv2.ROTATE_90_CLOCKWISE maps old top -> new right, old left -> new top, etc.
_ROTATIONS = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def _imread_unicode(path: str) -> np.ndarray | None:
    """Read a BGR image via imdecode so Chinese paths work."""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _rotate(image: np.ndarray, angle: int) -> np.ndarray:
    flag = _ROTATIONS.get(angle)
    return cv2.rotate(image, flag) if flag is not None else image


def _resize_to_max_side(image: np.ndarray, max_side: int = 1300) -> np.ndarray:
    """Upscale only (never downscale) so the long edge reaches max_side."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest >= max_side:
        return image
    scale = max_side / longest
    new_size = (int(round(w * scale)), int(round(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)


def _fit_to_max_side(image: np.ndarray, max_side: int = 1300) -> np.ndarray:
    """Downscale only (never upscale) so the long edge is at most max_side."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (int(round(w * scale)), int(round(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)


# --- quad detection -------------------------------------------------------

def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as [tl, tr, br, bl]."""
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]
    tr = pts[np.argmin(diff)]
    br = pts[np.argmax(s)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _find_quad(gray: np.ndarray) -> np.ndarray | None:
    """Detect the dominant card quad (4 unordered points) or None."""
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    min_area = gray.shape[0] * gray.shape[1] * 0.05
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(cnt)
        if area < min_area:
            break
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype(np.float32)
    return None


def _rotation_to_landscape(quad: np.ndarray) -> int:
    """Minimal rotation (0 or 90) so the card's long edge becomes horizontal."""
    q = _order_points(quad)
    edges = [q[1] - q[0], q[2] - q[1], q[3] - q[2], q[0] - q[3]]
    longest = max(edges, key=lambda v: v @ v)
    dx, dy = longest
    return 0 if abs(dx) >= abs(dy) else 90


def _dominant_rotation(gray: np.ndarray) -> int:
    """Landscape rotation (0 or 90) from the long-line angle histogram.

    Fallback when no card quad is found: assumes text lines dominate.
    """
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    min_len = max(30, min(gray.shape) // 8)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=80,
        minLineLength=min_len, maxLineGap=10,
    )
    if lines is None:
        return 0
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angles.append(np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180)
    hist, _ = np.histogram(angles, bins=36, range=(0, 180))
    peak = np.degrees((np.argmax(hist) + 0.5) * (180 / 36))
    # Vertical-dominant long edges -> rotate 90 to lay them horizontal.
    return 90 if 45 <= peak < 135 else 0


def _id_number_row_cy(bw: np.ndarray) -> float | None:
    """Relative y (0~1) of the ID-number row (the row with the most narrow
    runs, i.e. the 18-digit number at the bottom of an ID card), or None.

    The ID number is the row with the most digits; digits are much narrower
    than CJK glyphs, so counting narrow horizontal runs picks it out robustly.
    """
    h, w = bw.shape
    proj = np.count_nonzero(bw, axis=1)
    bands = []
    start = None
    for y in range(h):
        if proj[y] > 0 and start is None:
            start = y
        elif proj[y] == 0 and start is not None:
            bands.append((start, y))
            start = None
    if start is not None:
        bands.append((start, h))

    best_cy = None
    best_narrow = 0
    for y0, y1 in bands:
        row_h = y1 - y0
        if row_h > h * 0.12:
            continue  # a big text block, not a single row
        col = np.count_nonzero(bw[y0:y1], axis=0)
        narrow = 0
        in_run = False
        for x, v in enumerate(col):
            if v > 0 and not in_run:
                run_start = x
                in_run = True
            elif v == 0 and in_run:
                if x - run_start < row_h * 0.9:
                    narrow += 1
                in_run = False
        if in_run and w - run_start < row_h * 0.9:
            narrow += 1
        if narrow > best_narrow:
            best_narrow = narrow
            best_cy = (y0 + y1) / 2
    # An 18-digit ID number yields >= 8 narrow runs; below that it is noise.
    return best_cy / h if best_narrow >= 8 else None


def _is_upright(image: np.ndarray) -> bool:
    """Heuristic: is the card upright (not flipped 180)?

    Primary signal: the ID-number row (dense digits) sits in the lower half
    of an upright card. Falls back to upper-vs-lower text density.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if h < 20 or w < 20:
        return True

    # Primary: a dark-pixel threshold isolates the dark printed digits
    # without a global-invert decision. The old invert rule (dark pixels
    # < half) misjudges a card photographed on a light-gray background:
    # inverting turns the background into a foreground blob that swallows
    # the ID-number row, so an upright card is reported flipped (key
    # decision: threshold 100 keeps gray backgrounds (>=~170) out).
    _, darkbw = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    cy = _id_number_row_cy(darkbw)
    if cy is not None:
        return cy >= 0.5

    # Fallback: OTSU + invert, for text brighter than the background.
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = np.count_nonzero(bw == 0)
    if dark < bw.size - dark:
        bw = 255 - bw
    cy = _id_number_row_cy(bw)
    if cy is not None:
        return cy >= 0.5

    # Fallback: compare text density of upper vs lower half.
    top = bw[h // 8 : h // 2]
    bot = bw[h // 2 : h * 7 // 8]
    d_top = np.count_nonzero(top) / top.size
    d_bot = np.count_nonzero(bot) / bot.size
    return d_top >= d_bot


# --- public API -----------------------------------------------------------

def correct_orientation(image: np.ndarray) -> tuple[np.ndarray, int]:
    """Rotate the image upright; returns (rotated, clockwise_angle).

    angle is one of 0/90/180/270 and is the clockwise rotation applied to
    make the image upright. Long-edge analysis decides landscape vs portrait;
    the 0-vs-180 ambiguity is resolved by the text-density heuristic.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    quad = _find_quad(gray)
    if quad is not None:
        angle = _rotation_to_landscape(quad)
    else:
        angle = _dominant_rotation(gray)
    rotated = _rotate(image, angle)
    if not _is_upright(rotated):
        angle = (angle + 180) % 360
        rotated = _rotate(rotated, 180)
    return rotated, angle


def perspective_correct(image: np.ndarray) -> tuple[np.ndarray, list | None, bool]:
    """Detect the card quad and warp it axis-aligned. See spec-02 §3.3.2."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    quad = _find_quad(gray)
    if quad is None:
        return image, None, False
    q = _order_points(quad)
    tl, tr, br, bl = q
    width_a = np.linalg.norm(tr - tl)
    width_b = np.linalg.norm(br - bl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_w = max(int(round(width_a)), int(round(width_b)))
    max_h = max(int(round(height_a)), int(round(height_b)))
    if max_w < 10 or max_h < 10:
        return image, None, False
    dst = np.array([[0, 0], [max_w - 1, 0],
                    [max_w - 1, max_h - 1], [0, max_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(q, dst)
    warped = cv2.warpPerspective(image, matrix, (max_w, max_h))
    return warped, q.tolist(), True


def extract_foreground(image: np.ndarray, quad: list | None) -> np.ndarray:
    """Crop the card region defined by quad; pass-through when quad is None.

    Standalone helper used by callers that already know the quad. The main
    pipeline gets the crop for free from perspective_correct's warp.
    """
    if quad is None:
        return image
    try:
        q = _order_points(np.asarray(quad, dtype=np.float32))
        tl, tr, br, bl = q
        width_a = np.linalg.norm(tr - tl)
        width_b = np.linalg.norm(br - bl)
        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_w = max(int(round(width_a)), int(round(width_b)))
        max_h = max(int(round(height_a)), int(round(height_b)))
        if max_w < 10 or max_h < 10:
            return image
        dst = np.array([[0, 0], [max_w - 1, 0],
                        [max_w - 1, max_h - 1], [0, max_h - 1]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(q, dst)
        return cv2.warpPerspective(image, matrix, (max_w, max_h))
    except Exception:
        return image


def preprocess_image(image_path: str) -> PreprocessResult:
    """Full pipeline. Never raises; degrades to pass-through on failure.

    Call order: size normalize -> orientation correct -> perspective correct
    -> background removal. See spec-02 §3.2/§3.4.
    """
    image = _imread_unicode(image_path)
    if image is None:
        return PreprocessResult(error=f"cannot decode image: {image_path}")

    try:
        normalized = _resize_to_max_side(image, cfg.PREPROCESS_MAX_SIDE)
        rotated, angle = correct_orientation(normalized)
        corrected, quad, found = perspective_correct(rotated)
        final = corrected if found else rotated
        return PreprocessResult(
            image=final, rotation_angle=angle, quad=quad, found_card=found
        )
    except Exception:
        # spec-02 §3.4: degrade to pass-through, no exception, OCR still runs.
        return PreprocessResult(image=image)


def preprocess_document(image_path: str) -> PreprocessResult:
    """Light pipeline for full-page documents (invoices, receipts).

    Only decodes (Chinese-path safe) and caps the long edge: big scanned pages
    are downscaled to PREPROCESS_DOC_MAX_SIDE so OCR runs ~30% faster with no
    field loss (bench_invoice_scale), small pages pass through untouched. The
    card pipeline (orientation/perspective/background) is intentionally
    skipped: it mis-rotates and warps full-page layouts, destroying OCR
    (verified on the medical-receipt sample).
    """
    image = _imread_unicode(image_path)
    if image is None:
        return PreprocessResult(error=f"cannot decode image: {image_path}")

    try:
        return PreprocessResult(
            image=_fit_to_max_side(image, cfg.PREPROCESS_DOC_MAX_SIDE),
            rotation_angle=0, quad=None, found_card=False,
        )
    except Exception:
        return PreprocessResult(image=image)
