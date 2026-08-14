"""Invoice self-test: InvoiceProcessor extraction + light preprocess + UI wiring.

Checks:
1. Same-block labels (label+value glued) -> all five fields extracted.
2. Separate label/value blocks -> nearest-block geometry fallback.
3. Missing field (no 金额) -> recorded in `missing`, no exception.
4. VAT-invoice wording (发票代码/发票号码/价税合计/开票时间/购方名称) works.
5. Date normalized to YYYY-MM-DD (e.g. 2026年08月12日).
6. preprocess_document leaves a full-page layout untouched (no warp/crop).
7. Real-sample E2E: light preprocess -> OCR -> extract (skipped if sample gone).
8. MainWindow: 发票识别 tab enabled with invoice columns.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_invoice.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import src.config as cfg  # noqa: E402
from src.ocr.models import OcrResult, OcrWord  # noqa: E402
from src.processors import InvoiceProcessor, get_processor, registered_types  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402
from src.utils.preprocess import preprocess_document  # noqa: E402

SAMPLE = PROJECT_ROOT / "发票样张" / "微信图片_20260812103640_36_19.jpg"

EXPECTED = {"name": "唐洪发", "invoice_code": "32060226",
            "invoice_no": "0000243741", "amount": "4,180.76",
            "date": "2026-08-12"}


def make_word(text: str, x: int, y: int, w: int = 140, h: int = 30,
              conf: float = 0.98) -> OcrWord:
    return OcrWord(
        text=text,
        confidence=conf,
        box=[[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
    )


def _check(proc, words, expected, label, missing=()) -> None:
    r = proc.process(OcrResult(words=words))
    assert r.fields == expected, (label, r.fields)
    assert r.missing == list(missing), (label, r.missing)
    print(f"[ok] {label}: {r.fields}")


def main() -> int:
    proc = InvoiceProcessor()

    # 1. Same-block labels -> all fields.
    _check(proc, [
        make_word("交款人：唐洪发", 100, 100),
        make_word("票据代码：32060226", 100, 150),
        make_word("票据号码：0000243741", 100, 200),
        make_word("(小写)4,180.76", 100, 250),
        make_word("开票日期：2026-08-12", 100, 300),
    ], EXPECTED, "same-block labels")

    # 2. Separate label/value blocks -> geometry fallback (value to the right).
    _check(proc, [
        make_word("交款人：", 100, 100), make_word("唐洪发", 260, 105),
        make_word("票据代码：", 100, 160), make_word("32060226", 260, 165),
        make_word("票据号码：", 100, 220), make_word("0000243741", 260, 225),
        make_word("(小写)4,180.76", 100, 280),
        make_word("开票日期：", 100, 340), make_word("2026-08-12", 260, 345),
    ], EXPECTED, "separate label/value blocks")

    # 3. Missing 金额 -> recorded, no exception.
    r = proc.process(OcrResult(words=[
        make_word("交款人：唐洪发", 100, 100),
        make_word("票据代码：32060226", 100, 150),
        make_word("票据号码：0000243741", 100, 200),
        make_word("开票日期：2026-08-12", 100, 250),
    ]))
    assert r.missing == ["amount"], r.missing
    assert r.fields["name"] == "唐洪发"
    print(f"[ok] missing amount recorded: {r.missing}")

    # 4. VAT-invoice wording + Chinese 大写 fallback for amount.
    _check(proc, [
        make_word("购方名称：北京某某科技公司", 100, 100),
        make_word("发票代码：12345678", 100, 150),
        make_word("发票号码：123456789012", 100, 200),
        make_word("价税合计（大写）壹仟贰佰叁拾肆元整", 100, 250),
        make_word("开票时间：2024-01-02", 100, 300),
    ], {"name": "北京某某科技公司", "invoice_code": "12345678",
        "invoice_no": "123456789012", "amount": "壹仟贰佰叁拾肆元整",
        "date": "2024-01-02"}, "VAT wording + 大写 fallback")

    # 5. Date normalization.
    _check(proc, [
        make_word("交款人：唐洪发", 100, 100),
        make_word("票据代码：32060226", 100, 150),
        make_word("票据号码：0000243741", 100, 200),
        make_word("(小写)4,180.76", 100, 250),
        make_word("开票日期：2026年08月12日", 100, 300),
    ], {**EXPECTED, "date": "2026-08-12"}, "date normalization")

    # 6. preprocess_document: full-page layout untouched (no warp/crop), long
    #    side capped at PREPROCESS_DOC_MAX_SIDE (downscale-only).
    if SAMPLE.exists():
        pre = preprocess_document(str(SAMPLE))
        assert pre.error is None, pre.error
        assert pre.found_card is False
        assert not hasattr(pre, "quad") or pre.quad is None
        h, w = pre.image.shape[:2]
        assert max(h, w) <= cfg.PREPROCESS_DOC_MAX_SIDE, (h, w)
        print(f"[ok] preprocess_document caps long side ({w}x{h})")
    else:
        print("[skip] preprocess_document (sample missing)")

    # 7. Real-sample E2E (light preprocess -> OCR -> extract).
    if SAMPLE.exists():
        from src.ocr.engine import get_engine  # noqa: E402
        pre = preprocess_document(str(SAMPLE))
        tmp = Path(tempfile.gettempdir()) / "invoice_e2e.png"
        cv2.imencode(".png", pre.image)[1].tofile(str(tmp))
        res = get_engine().recognize(str(tmp))
        tmp.unlink(missing_ok=True)
        assert res.error is None, res.error
        assert len(res.words) > 0
        r = proc.process(res)
        assert r.fields == EXPECTED, r.fields
        assert r.missing == [], r.missing
        print("[ok] real-sample E2E all 5 fields correct")
    else:
        print("[skip] real-sample E2E (sample missing)")

    # 8. MainWindow: invoice tab enabled + invoice columns.
    app = QApplication(sys.argv)
    window = MainWindow()
    tabs = window.centralWidget()
    assert tabs.isTabEnabled(0) is True and tabs.isTabEnabled(1) is True
    headers = [window._invoice_page.result_table.horizontalHeaderItem(i).text()
               for i in range(window._invoice_page.result_table.columnCount())]
    assert headers == ["序号", "姓名", "发票代码", "发票号码", "金额", "开票时间"], headers
    print("[ok] 发票识别 tab enabled, invoice columns:", headers)

    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
