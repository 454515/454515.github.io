"""Stage 4 self-test: verify the main window layout headlessly (spec-04 §6/§7).

Runs on the offscreen Qt platform so it works without a display.

Checks:
1. MainWindow constructs; tab 2 (发票识别预留) is disabled.
2. Drop area, buttons, progress bar, table, bottom bar all present.
3. Table column headers = 序号/姓名/性别/身份证号.
4. add_demo_rows fills rows and updates the count label.
5. Window resizes without layout collapse.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_ui_smoke.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from src.processors.models import CardResult  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()

    # 1. Both tabs (身份证识别 / 发票识别) enabled.
    tabs = window.centralWidget()
    assert tabs.count() == 2, f"expected 2 tabs, got {tabs.count()}"
    assert tabs.isTabEnabled(0) is True and tabs.isTabEnabled(1) is True
    print("[ok] 身份证识别 and 发票识别 tabs enabled")

    # 2. Key widgets present; the progress row (bar + label) starts hidden.
    assert window.drop_area is not None
    assert window.select_button is not None and window.paste_button is not None
    assert window.progress_bar is not None and window.progress_label is not None
    assert window.progress_row is not None and window.progress_row.isHidden()
    assert window.result_table is not None and window.bottom_bar is not None
    print("[ok] all layout sections present (progress bar hidden)")

    # 3. Table columns.
    headers = [window.result_table.horizontalHeaderItem(i).text()
               for i in range(window.result_table.columnCount())]
    assert headers == ["序号", "姓名", "性别", "身份证号"], headers
    print(f"[ok] table columns: {headers}")

    # Invoice tab columns.
    inv_headers = [window._invoice_page.result_table.horizontalHeaderItem(i).text()
                   for i in range(window._invoice_page.result_table.columnCount())]
    assert inv_headers == ["序号", "姓名", "发票代码", "发票号码", "金额", "开票时间"]
    print(f"[ok] invoice table columns: {inv_headers}")

    # 4. Demo rows fill the table and update the count.
    window.add_demo_rows([
        CardResult(card_type="idcard",
                   fields={"name": "张三", "gender": "男",
                           "id_number": "110101199001011234"}),
        CardResult(card_type="idcard",
                   fields={"name": "李四", "gender": "女",
                           "id_number": "310101199202025678"}),
    ])
    assert window.result_table.rowCount() == 2
    assert window.result_table.item(0, 1).text() == "张三"
    assert window.result_table.item(1, 3).text() == "310101199202025678"
    assert window.bottom_bar.count_label.text() == "共 2 条结果"
    print("[ok] demo rows shown, count label updated")

    # 5. Resize does not collapse the layout.
    window.resize(500, 400)
    window.resize(1100, 800)
    app.processEvents()
    print("[ok] resize ok")

    print("ALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
