"""IDCardProcessor - extract name/gender/ID number from OCR words. spec-03 §5.

Rules:
- name: find the 姓名 label block, then take CJK text right after the label in
  the same block, or the nearest CJK block to the label's lower-right (works
  for both horizontal and vertical layouts).
- gender: prefer 男/女 inside a 性别 block, else a standalone 男/女 block.
- id_number: regex \\d{17}[\\dXx] across all blocks, pick the highest-confidence
  match; trailing x is normalized to uppercase X.
"""
import re

from src.ocr.models import OcrResult
from src.processors.base import BaseProcessor
from src.processors.models import CardResult

ID_NO_RE = re.compile(r"\d{17}[\dXx]")
# Label-ish text that must never be picked as a name value.
_LABEL_KEYWORDS = (
    "姓名", "性别", "民族", "出生", "住址", "公民", "身份",
    "号码", "签发", "有效",
)


def validate_id_number(id_no: str) -> bool:
    """18 digits, first 17 numeric, last digit or uppercase X (spec-02 §5.4)."""
    if not id_no or len(id_no) != 18:
        return False
    if not id_no[:17].isdigit():
        return False
    return id_no[-1].isdigit() or id_no[-1] == "X"


def _box_center(word) -> tuple[float, float] | None:
    if not word.box:
        return None
    xs = [p[0] for p in word.box]
    ys = [p[1] for p in word.box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _is_chinese_name(text: str) -> bool:
    t = text.replace("·", "").strip()
    return 1 <= len(t) <= 4 and all("一" <= c <= "龥" for c in t)


def _extract_name(words: list) -> str | None:
    label, label_pos = None, None
    for i, w in enumerate(words):
        if "姓名" not in w.text:
            continue
        label, label_pos = w, i
        # Name glued to the label in the same block, e.g. "姓名 张建邺".
        rest = re.sub(r"^姓名[\s:：]*", "", w.text)
        if _is_chinese_name(rest):
            return rest
        break
    if label is None:
        return None

    label_center = _box_center(label)
    best, best_dist = None, float("inf")
    for j, w in enumerate(words):
        if j == label_pos:
            continue
        cand = re.sub(r"\s+", "", w.text)
        if not _is_chinese_name(cand) or any(k in cand for k in _LABEL_KEYWORDS):
            continue
        if label_center is None:
            return cand  # no geometry: take the first CJK block after the label
        wc = _box_center(w)
        if wc is None:
            continue
        dx, dy = wc[0] - label_center[0], wc[1] - label_center[1]
        if dx < -20 or dy < -20:
            continue  # block sits upper-left of the label: not a value
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best, best_dist = cand, dist
    return best


def _extract_gender(words: list) -> str | None:
    for w in words:
        if "性别" in w.text:
            m = re.search(r"[男女]", w.text)
            if m:
                return m.group()
    # Fallback: a standalone single-char 男/女 block.
    for w in words:
        t = w.text.strip()
        if t in ("男", "女"):
            return t
    return None


def _extract_id_number(words: list) -> str | None:
    best, best_conf = None, -1.0
    for w in words:
        text = re.sub(r"\s+", "", w.text)
        for m in ID_NO_RE.finditer(text):
            conf = w.confidence if w.confidence else 0.0
            if conf > best_conf:
                best, best_conf = m.group(), conf
    return best


class IDCardProcessor(BaseProcessor):
    card_type = "idcard"

    def process(self, ocr_result: OcrResult) -> CardResult:
        words = ocr_result.words if ocr_result else []
        fields: dict[str, str] = {}
        missing: list[str] = []

        name = _extract_name(words)
        if name:
            fields["name"] = name
        else:
            missing.append("name")

        gender = _extract_gender(words)
        if gender:
            fields["gender"] = gender
        else:
            missing.append("gender")

        id_no = _extract_id_number(words)
        if id_no:
            id_no = id_no[:-1] + id_no[-1].upper()  # normalize trailing x -> X
            fields["id_number"] = id_no
            if not validate_id_number(id_no):
                missing.append("id_number")  # mark only, keep the value (spec §5.4)
        else:
            missing.append("id_number")

        return CardResult(card_type=self.card_type, fields=fields, missing=missing)
