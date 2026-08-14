"""Stage 6 self-test: batch recognition + result management (spec-06 §7).

Headless (offscreen) checks:
1. RecognitionService: 3 images (1 bad) -> 2 ok + 1 skipped, progress
   sequence, one result per image, batch_finished(failed=1).
2. RecognitionService.stop(): a slow batch stops early.
3. MainWindow end-to-end: import real images -> rows appear; a corrupt
   image -> a 识别失败 row.
4. Copy-all -> clipboard tab-separated text with header, Excel-friendly.
5. Double-click editing enabled; editing a cell updates the table.
6. Delete a row -> renumbered; clear -> zero rows.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_stage6.py
"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QItemSelection, QItemSelectionModel, Qt  # noqa: E402
from PySide6.QtGui import QKeySequence, QShortcut  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QApplication,
    QLineEdit,
)

from src.core.import_queue import ImportedImage  # noqa: E402
from src.core.recognition_service import RecognitionService  # noqa: E402
from src.processors.models import CardResult  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402

NAME, GENDER, ID_NO = "张三", "男", "110101199001011234"


class _FakeEngine:
    def recognize(self, path):
        return SimpleNamespace(error=None, words=[])


class _SlowEngine(_FakeEngine):
    def recognize(self, path):
        time.sleep(0.3)
        return SimpleNamespace(error=None, words=[])


class _FakeProcessor:
    def process(self, ocr):
        return CardResult(card_type="idcard",
                          fields={"name": NAME, "gender": GENDER,
                                  "id_number": ID_NO}, missing=[])


class _FakePreprocess:
    def __init__(self, fail=()):
        self._fail = set(fail)

    def __call__(self, path):
        if str(path) in self._fail:
            return None
        return SimpleNamespace(image=np.zeros((8, 8, 3), np.uint8), error=None)


def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.full((40, 80, 3), 200, np.uint8))


def _wait_rows(window, expected, timeout=15000) -> int:
    waited = 0
    while window.result_table.rowCount() < expected and waited < timeout:
        QTest.qWait(50)
        waited += 50
    return window.result_table.rowCount()


def _run_service(service, images, timeout=15000) -> int:
    """Run to completion; returns batch_finished's failed count."""
    done = []
    service.batch_finished.connect(done.append)
    service.start_batch(images)
    waited = 0
    while not done and waited < timeout:
        QTest.qWait(50)
        waited += 50
    assert done, "batch did not finish"
    service._thread.join(2.0)
    return done[0]


def main() -> int:
    app = QApplication(sys.argv)
    workdir = Path(tempfile.mkdtemp(prefix="stage6_"))
    try:
        # --- 1. RecognitionService batch: skip + failure count ---
        p1, p2 = workdir / "a.png", workdir / "b.png"
        bad = workdir / "bad.png"
        _make_image(p1)
        _make_image(p2)
        images = [ImportedImage(str(p1), "a.png"),
                  ImportedImage(str(bad), "bad.png"),
                  ImportedImage(str(p2), "b.png")]
        service = RecognitionService(_FakeEngine(),
                                     _FakePreprocess(fail={str(bad)}),
                                     _FakeProcessor())
        results, progresses = [], []
        service.result_ready.connect(lambda r, p: results.append((r, p)))
        service.progress_updated.connect(lambda c, t: progresses.append((c, t)))
        failed = _run_service(service, images)
        assert failed == 1, failed
        assert len(results) == 3
        assert progresses == [(0, 3), (1, 3), (2, 3)]
        assert results[0][0].fields["name"] == NAME
        assert results[1][0].fields == {}  # skipped -> empty fields
        assert results[2][0].fields["name"] == NAME
        print("[ok] RecognitionService batch, skip + failure count")

        # --- 2. stop(): slow batch stops early ---
        many = [ImportedImage(str(p1), f"x{i}.png") for i in range(5)]
        service2 = RecognitionService(_SlowEngine(), _FakePreprocess(),
                                      _FakeProcessor())
        results2 = []
        service2.result_ready.connect(lambda r, p: results2.append(r))
        _run_service(service2, many)  # sanity: no stop runs all 5
        assert len(results2) == 5

        service3 = RecognitionService(_SlowEngine(), _FakePreprocess(),
                                      _FakeProcessor())
        results3 = []
        service3.result_ready.connect(lambda r, p: results3.append(r))
        done3 = []
        service3.batch_finished.connect(done3.append)
        service3.start_batch(many)
        service3.stop()
        waited = 0
        while not done3 and waited < 15000:
            QTest.qWait(50)
            waited += 50
        assert done3
        assert len(results3) < 5, len(results3)
        service3._thread.join(2.0)
        print("[ok] RecognitionService.stop() stops early")

        # --- 3. MainWindow end-to-end incl. corrupt image ---
        window = MainWindow(engine=_FakeEngine(), processor=_FakeProcessor())
        good = workdir / "good1.jpg"
        badfile = workdir / "bad.jpg"
        _make_image(good)
        badfile.write_bytes(b"not an image")
        window._import_paths([str(good), str(badfile), str(p2)])
        _wait_rows(window, 3)
        assert window.result_table.item(0, 1).text() == NAME
        assert window.result_table.item(1, 1).text() == "识别失败"
        assert window.bottom_bar.count_label.text() == "共 3 条结果"
        print("[ok] MainWindow end-to-end, corrupt image -> 识别失败")

        # --- 4. copy-all -> Excel-safe clipboard (HTML + plain text) ---
        # Cell-level selection: single-click picks a cell, drag selects a region.
        assert window.result_table.selectionBehavior() == QAbstractItemView.SelectItems
        assert any(s.key() == QKeySequence.Copy
                   for s in window.findChildren(QShortcut))
        window._copy_all()
        lines = QApplication.clipboard().text().splitlines()
        assert lines[0] == "序号\t姓名\t性别\t身份证号"
        assert len(lines) == 4  # header + 3 rows
        for line in lines[1:]:
            assert len(line.split("\t")) == 4
        # HTML flavour carries mso-number-format:@ so Excel keeps IDs as text.
        html = QApplication.clipboard().mimeData().html()
        assert "mso-number-format:\\@" in html, html
        assert ID_NO in html and NAME in html, html
        # Copy-selected: picking just the 身份证号 cell copies that one column
        # (its header + the value), still HTML mso-number-format so Excel
        # keeps the 18-digit ID as text — the exact scenario that used to
        # paste as 3.21322E+17 from the double-click edit box.
        model = window.result_table.model()
        sm = window.result_table.selectionModel()
        sm.clear()
        sm.select(QItemSelection(model.index(0, 3), model.index(0, 3)),
                  QItemSelectionModel.ClearAndSelect)
        window._copy_selected()
        lines = QApplication.clipboard().text().splitlines()
        assert lines[0] == "身份证号", lines
        assert ID_NO in lines[1], lines
        assert ID_NO in QApplication.clipboard().mimeData().html()
        print("[ok] copy-all / copy-selected -> HTML mso-number-format + TSV")

        # --- 5. double-click editing enabled + edit updates table ---
        assert window.result_table.editTriggers() & QAbstractItemView.DoubleClicked
        window.result_table.item(0, 1).setText("李四")
        assert window.result_table.item(0, 1).text() == "李四"
        assert window.result_table.rows_data()[1][1] == "李四"
        print("[ok] double-click editing enabled, cell edit works")

        # --- 6. delete a row -> renumber; clear -> zero ---
        window.result_table.selectRow(1)
        window._delete_selected()
        assert window.result_table.rowCount() == 2
        assert [window.result_table.item(r, 0).text() for r in range(2)] == ["1", "2"]
        assert window.bottom_bar.count_label.text() == "共 2 条结果"
        window._do_clear()  # bypass the confirm dialog
        assert window.result_table.rowCount() == 0
        assert window.bottom_bar.count_label.text() == "共 0 条结果"
        print("[ok] delete renumber + clear to zero")

        # --- 7. single-click opens the editor with all text selected; ---
        #     Ctrl+C inside the editor copies Excel-safe HTML + TSV ---
        window.result_table.append_row(["1", NAME, GENDER, ID_NO])
        rect = window.result_table.visualItemRect(window.result_table.item(0, 1))
        QTest.mouseClick(window.result_table.viewport(), Qt.LeftButton,
                         Qt.NoModifier, rect.center())
        QTest.qWait(50)
        editor = window.result_table.indexWidget(window.result_table.currentIndex())
        assert isinstance(editor, QLineEdit), editor
        assert editor.selectedText() == NAME, editor.selectedText()
        # Ctrl+C in the editor must paste via the Excel-safe dual flavour
        # (the scenario that used to paste the ID as 3.21322E+17).
        QTest.keyClick(editor, Qt.Key_C, Qt.ControlModifier)
        assert QApplication.clipboard().text() == NAME
        html = QApplication.clipboard().mimeData().html()
        assert "mso-number-format:\\@" in html and NAME in html, html
        print("[ok] single-click text-select + in-editor Ctrl+C -> Excel-safe")

        print("ALL OK")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
