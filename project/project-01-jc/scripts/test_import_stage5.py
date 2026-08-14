"""Stage 5 self-test: image import paths (spec-05 §7/§8).

Queue logic (headless) plus UI-level checks on the offscreen Qt platform:
1. add_images: two files -> queued in order.
2. add_folder: nested subdirs scanned, name-sorted.
3. add_images with a .txt -> rejected, no crash.
4. Duplicate path -> added once only.
5. MainWindow._import_paths(files + folders) -> queue updated, status feedback.
6. Clipboard image paste (Ctrl+V handler) -> queued.
7. DropArea drag-enter -> highlighted; drop -> paths emitted into the queue.

Usage:
    .venv\\Scripts\\python.exe scripts\\test_import_stage5.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QImage,
)
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from src.core.import_queue import ImportQueue  # noqa: E402
from src.processors.models import CardResult  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402


class _EchoEngine:
    def recognize(self, path):
        return SimpleNamespace(error=None, words=[])


class _EchoProcessor:
    def process(self, ocr):
        return CardResult(card_type="idcard",
                          fields={"name": "张三", "gender": "男",
                                  "id_number": "110101199001011234"},
                          missing=[])


def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.zeros((10, 10, 3), np.uint8))


def _wait_rows(window, expected, timeout=15000) -> int:
    """Spin the event loop until the table reaches expected rows."""
    waited = 0
    while window.result_table.rowCount() < expected and waited < timeout:
        QTest.qWait(50)
        waited += 50
    return window.result_table.rowCount()


def main() -> int:
    app = QApplication(sys.argv)
    workdir = Path(tempfile.mkdtemp(prefix="stage5_"))
    try:
        # --- 1. add_images, order preserved ---
        q = ImportQueue()
        p1, p2 = workdir / "b.png", workdir / "a.jpg"
        _make_image(p1)
        _make_image(p2)
        accepted = q.add_images([str(p1), str(p2)])
        assert accepted == [str(p1), str(p2)]
        assert [i.filename for i in q.items()] == ["b.png", "a.jpg"]
        print("[ok] add_images order preserved")

        # --- 2. add_folder, recursive + name-sorted ---
        folder = workdir / "dir"
        _make_image(folder / "z.png")
        _make_image(folder / "sub" / "a.jpg")
        _make_image(folder / "sub" / "m.jpeg")
        (folder / "sub" / "note.txt").write_text("x")
        accepted = q.add_folder(str(folder))
        names = sorted(Path(p).name for p in accepted)
        assert names == ["a.jpg", "m.jpeg", "z.png"], names
        print("[ok] add_folder recursive + sorted")

        # --- 3. non-image rejected, no crash ---
        txt = workdir / "notes.txt"
        txt.write_text("hello")
        q2 = ImportQueue()
        q2.add_images([str(p1), str(txt)])
        rejected = q2.take_rejected()
        assert rejected == [str(txt)], rejected
        assert len(q2.items()) == 1
        print("[ok] non-image rejected")

        # --- 4. de-duplication ---
        q3 = ImportQueue()
        q3.add_images([str(p1), str(p1)])
        assert len(q3.items()) == 1
        q3.add_images([str(p1)])  # same path again
        assert len(q3.items()) == 1
        print("[ok] duplicate path added once")

        # --- 5. MainWindow._import_paths (files + folder) drives recognition ---
        window = MainWindow(engine=_EchoEngine(), processor=_EchoProcessor())
        png = workdir / "drag1.png"
        _make_image(png)
        window._import_paths([str(png), str(folder)])  # 1 png + 3 in folder
        assert _wait_rows(window, 4) == 4
        print("[ok] _import_paths files + folder recognized into table")

        # --- 6. clipboard paste ---
        img = QImage(10, 10, QImage.Format_RGB32)
        img.fill(QColor("red"))
        QApplication.clipboard().setImage(img)
        window._paste_clipboard()
        assert _wait_rows(window, 5) == 5
        print("[ok] clipboard image paste recognized")

        # --- 7. DropArea highlight + drop drives recognition ---
        drop_file = workdir / "drop2.jpg"
        _make_image(drop_file)
        area = window.drop_area
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(drop_file))])
        enter = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, mime,
                                Qt.LeftButton, Qt.NoModifier)
        area.dragEnterEvent(enter)
        assert enter.isAccepted() and area.is_highlighted
        print("[ok] drag-enter highlighted")
        drop = QDropEvent(QPoint(5, 5), Qt.CopyAction, mime,
                          Qt.LeftButton, Qt.NoModifier)
        area.dropEvent(drop)
        assert area.is_highlighted is False
        assert _wait_rows(window, 6) == 6
        print("[ok] drop recognized, highlight restored")

        print("ALL OK")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
