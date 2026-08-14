"""InvoiceProcessor - extract name/code/number/amount/date from OCR words.

Anchored extraction: locate the block containing a field's label (交款人 /
票据代码 / 票据号码 / 开票日期, plus VAT-invoice wording 发票代码 / 发票号码 /
开票时间), take the value glued after the label in the same block, and fall
back to the nearest block to the label's lower-right. amount prefers the 小写
numeric value (e.g. "(小写)4,180.76") and falls back to the Chinese 大写 value
from a 金额合计/价税合计 block.
"""
import re

from src.ocr.models import OcrResult
from src.processors.base import BaseProcessor
from src.processors.models import CardResult

_CN_NUM = "零壹贰叁肆伍陆柒捌玖拾佰仟万亿整正元角分"
_NUM_RE = r"\d[\d,]*\.\d{1,2}"
_DATE_RE = r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}"


def _box_center(word) -> tuple[float, float] | None:
    if not word.box:
        return None
    xs = [p[0] for p in word.box]
    ys = [p[1] for p in word.box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _strip_label(text: str, label: str) -> str:
    """Text after the label, minus a leading : ： and whitespace."""
    idx = text.find(label)
    if idx < 0:
        return ""
    return text[idx + len(label):].lstrip(" :：")


# ---- field validators / extractors ---------------------------------------

def _is_name(s: str) -> bool:
    return 1 <= len(s) <= 20 and all("一" <= c <= "龥" for c in s)


def _is_code(s: str) -> bool:
    return bool(re.fullmatch(r"\d{8,12}", s))


def _is_number(s: str) -> bool:
    return bool(re.fullmatch(r"\d{8,20}", s))


def _normalize_date(s: str) -> str:
    m = re.fullmatch(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", s)
    if m is None:
        return s
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _is_cn_amount(s: str) -> bool:
    return 1 <= len(s) <= 20 and all(c in _CN_NUM for c in s)


def _name_extract(text: str) -> str | None:
    s = re.sub(r"\s+", "", text)
    return s if _is_name(s) else None


def _code_extract(text: str) -> str | None:
    s = re.sub(r"\s+", "", text)
    return s if _is_code(s) else None


def _no_extract(text: str) -> str | None:
    s = re.sub(r"\s+", "", text)
    return s if _is_number(s) else None


def _date_extract(text: str) -> str | None:
    m = re.search(_DATE_RE, text)
    return _normalize_date(m.group()) if m else None


def _value_after_label(words: list, labels: tuple, extract) -> str | None:
    """Value for the first block containing a label, then nearest-block fallback."""
    label_pos = None
    for i, w in enumerate(words):
        text = w.text
        matched = next((lab for lab in labels if lab in text), None)
        if matched is None:
            continue
        rest = _strip_label(text, matched)
        if rest:
            value = extract(rest)
            if value is not None:
                return value
        label_pos = i
        break
    if label_pos is None:
        return None

    lc = _box_center(words[label_pos])
    if lc is None:
        return None
    best, best_dist = None, float("inf")
    for j, w in enumerate(words):
        if j == label_pos:
            continue
        value = extract(w.text)
        if value is None:
            continue
        wc = _box_center(w)
        if wc is None:
            continue
        dx, dy = wc[0] - lc[0], wc[1] - lc[1]
        if dx < -30 or dy < -30:
            continue  # block sits upper-left of the label: not a value
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best, best_dist = value, dist
    return best


def _extract_amount(words: list) -> str | None:
    # 1) numeric 小写 value — "(小写)4,180.76"
    for w in words:
        if "小写" in w.text:
            m = re.search(_NUM_RE, w.text)
            if m:
                return m.group()
    # 2) 金额合计 / 价税合计 block: numeric first, then Chinese 大写.
    for w in words:
        for label in ("金额合计", "价税合计", "金额"):
            if label in w.text:
                m = re.search(_NUM_RE, w.text)
                if m:
                    return m.group()
                rest = _strip_label(w.text, label)
                rest = re.sub(r"[（(]?大写[）)]?", "", rest)
                rest = re.sub(r"\s+", "", rest)
                if _is_cn_amount(rest):
                    return rest
                break
    return None


class InvoiceProcessor(BaseProcessor):
    card_type = "invoice"

    def process(self, ocr_result: OcrResult) -> CardResult:
        words = ocr_result.words if ocr_result else []
        fields: dict[str, str] = {}
        missing: list[str] = []

        anchored = [
            ("name", ("交款人", "姓名", "购方名称", "购买方名称"), _name_extract),
            ("invoice_code", ("票据代码", "发票代码"), _code_extract),
            ("invoice_no", ("票据号码", "发票号码"), _no_extract),
            ("date", ("开票日期", "开票时间"), _date_extract),
        ]
        for key, labels, extract in anchored:
            value = _value_after_label(words, labels, extract)
            if value:
                fields[key] = value
            else:
                missing.append(key)

        amount = _extract_amount(words)
        if amount:
            fields["amount"] = amount
        else:
            missing.append("amount")

        return CardResult(card_type=self.card_type, fields=fields, missing=missing)
