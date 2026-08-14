"""RecognitionPage - self-contained recognition workspace for one doc type.

Owns the drop area, import buttons, progress row, results table and bottom
bar, plus the import queue and background recognition service for a single
document type. MainWindow hosts one page per tab (idcard / invoice); each page
is fully independent — a separate result table and its own batch runs.

This logic was lifted from MainWindow (spec-05/06) so every document type
shares the same interaction: import -> auto-recognize -> edit/copy/delete.
Global keyboard shortcuts (Ctrl+V / Ctrl+C) live on MainWindow and dispatch
here, since an ApplicationShortcut on every page would fire twice.
"""
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.import_queue import ImportQueue
from src.core.recognition_service import RecognitionService
from src.processors.models import CardResult
from src.ui.bottom_bar import BottomBar
from src.ui.clipboard import put_excel_clipboard
from src.ui.drop_area import DropArea
from src.ui.result_table import ResultTable

IMAGE_FILTER = "图片文件 (*.jpg *.jpeg *.png *.bmp)"


class RecognitionPage(QWidget):
    recognition_finished = Signal(int)  # failed count

    def __init__(self, columns: list[str], fields: list[str], processor,
                 preprocess, engine, warmup=None, parent=None) -> None:
        super().__init__(parent)
        self._columns = list(columns)
        self._fields = list(fields)
        self._processor = processor
        self._preprocess = preprocess
        self._engine = engine
        self._warmup = warmup
        self.import_queue = ImportQueue()
        self._service: RecognitionService | None = None
        self._temp_files: list[Path] = []  # clipboard paste temps
        self._build_layout()

        self.drop_area.dropped_paths.connect(self._import_paths)
        self.select_button.clicked.connect(self._select_files)
        self.paste_button.clicked.connect(self._paste_clipboard)
        self.bottom_bar.copy_button.clicked.connect(self._copy_all)
        self.bottom_bar.clear_button.clicked.connect(self._clear_all)
        self.result_table.delete_requested.connect(self._delete_selected)
        self.result_table.copy_selected_requested.connect(self._copy_selected)

    def stop_and_cleanup(self) -> None:
        """Stop any running batch and clean clipboard temp files (closeEvent)."""
        if self._service is not None:
            self._service.stop()
        for f in self._temp_files:
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        self._temp_files.clear()

    # ---- import actions ----

    def _import_paths(self, paths: list[str]) -> None:
        """Add dropped/selected paths (files and/or folders) to the queue."""
        files, folders = [], []
        for p in paths:
            (folders if Path(p).is_dir() else files).append(str(p))
        accepted = self.import_queue.add_images(files)
        for folder in folders:
            accepted += self.import_queue.add_folder(folder)
        rejected = self.import_queue.take_rejected()
        if rejected:
            self.statusBarMessage(
                f"已导入 {len(accepted)} 张，跳过 {len(rejected)} 个非图片文件")
        elif accepted:
            self.statusBarMessage(f"已导入 {len(accepted)} 张图片")
        if accepted:
            self._start_recognition()

    def _select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", IMAGE_FILTER)
        if paths:
            self._import_paths(paths)

    def _paste_clipboard(self) -> None:
        """Handle Ctrl+V or paste button click (bitmap -> URLs -> WeChat JSON)."""
        import json

        mime = QApplication.clipboard().mimeData()

        if mime.hasImage():
            image = QApplication.clipboard().image()
            if image.isNull():
                self.statusBarMessage("剪贴板图片为空，无法粘贴")
                return
            tmp = Path(tempfile.gettempdir()) / f"clipboard_{time.time()}.png"
            if image.save(str(tmp), "PNG"):
                self._temp_files.append(tmp)
                self._import_paths([str(tmp)])
            return

        if mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            if paths:
                self._import_paths(paths)
                return

        wechat_fmt = (
            'application/x-qt-windows-mime;value="x-xwechat-multiselect-copy"'
        )
        if mime.hasFormat(wechat_fmt):
            data = mime.data(wechat_fmt)
            try:
                items = json.loads(bytes(data).decode("utf-8"))
                paths = [item["file"] for item in items if "file" in item]
                if paths:
                    self._import_paths(paths)
                    return
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                pass

        self.statusBarMessage("剪贴板中没有图片（Ctrl+V 或点粘贴图片按钮）")

    def statusBarMessage(self, msg: str) -> None:
        """Show a message; no QMainWindow here, so keep it minimal."""
        parent = self.window()
        if hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(msg, 3000)

    # ---- recognition ----

    def _start_recognition(self) -> None:
        """Snapshot the queue and run a background batch; never blocks UI."""
        if self._warmup is not None:
            self._warmup()  # async + idempotent; engine lock makes predict wait
        if self._service is not None and self._service.is_running():
            return  # mid-run imports drain in a follow-up batch
        items = self.import_queue.items()
        self.import_queue.clear()
        if not items:
            return
        if len(items) == 1:
            self.progress_row.hide()
        else:
            self.progress_bar.setRange(0, len(items))
            self.progress_bar.setValue(0)
            self.progress_row.show()
        self._service = RecognitionService(self._engine, self._preprocess,
                                           self._processor)
        self._service.progress_updated.connect(self._on_progress)
        self._service.image_started.connect(self._on_image_started)
        self._service.result_ready.connect(self._on_result)
        self._service.batch_finished.connect(self._on_batch_finished)
        self._service.start_batch(items)

    def _on_image_started(self, filename: str) -> None:
        self.statusBarMessage(f"正在识别 {filename}")

    def _on_progress(self, current: int, total: int) -> None:
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"正在识别第 {current + 1} 张 / 共 {total} 张")

    def _on_result(self, result: CardResult, path: str) -> None:
        if result.fields:
            cells = [self.result_table.rowCount() + 1] + [
                result.fields.get(k, "") for k in self._fields]
        else:
            cells = [self.result_table.rowCount() + 1] + \
                ["识别失败"] * len(self._fields)
        self.result_table.append_row(cells)
        self.bottom_bar.set_count(self.result_table.rowCount())

    def _on_batch_finished(self, failed: int) -> None:
        self.progress_row.hide()
        self.progress_bar.setValue(self.progress_bar.maximum())
        msg = f"完成，失败 {failed} 张" if failed else "识别完成"
        self.statusBarMessage(msg)
        self.recognition_finished.emit(failed)
        if self.import_queue.items():
            self._start_recognition()  # drain anything imported mid-run

    # ---- result management ----

    def _copy_all(self) -> None:
        data = self.result_table.rows_data()
        if len(data) <= 1:
            return
        put_excel_clipboard(data)
        self.statusBarMessage(f"已复制 {len(data) - 1} 条")

    def _copy_selected(self) -> None:
        data = self.result_table.selected_cells_data()
        if len(data) <= 1:
            return
        put_excel_clipboard(data)
        self.statusBarMessage("已复制选中区域")

    def _delete_selected(self) -> None:
        rows = sorted({i.row() for i in self.result_table.selectedIndexes()},
                      reverse=True)
        for r in rows:
            self.result_table.removeRow(r)
        self.result_table.renumber()
        self.bottom_bar.set_count(self.result_table.rowCount())

    def _clear_all(self) -> None:
        if QMessageBox.question(self, "清空", "确定要清空所有结果吗？") == QMessageBox.Yes:
            self._do_clear()

    def _do_clear(self) -> None:
        self.result_table.setRowCount(0)
        self.bottom_bar.set_count(0)
        self.statusBarMessage("已清空")

    # ---- helpers ----

    def add_demo_rows(self, rows: list[CardResult]) -> None:
        """Fill the table with demo rows (stage-4 placeholder, tests only)."""
        data = [[str(i + 1)] + [r.fields.get(k, "") for k in self._fields]
                for i, r in enumerate(rows)]
        self.result_table.set_rows(data)
        self.bottom_bar.set_count(len(data))

    def _build_layout(self) -> None:
        self.drop_area = DropArea()
        self.select_button = QPushButton("选择文件")
        self.paste_button = QPushButton("粘贴图片")
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel()
        self.progress_row = QWidget()
        prog_layout = QHBoxLayout(self.progress_row)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.addWidget(self.progress_bar, stretch=1)
        prog_layout.addWidget(self.progress_label)
        self.progress_row.hide()
        self.result_table = ResultTable(self._columns)
        self.bottom_bar = BottomBar()

        button_row = QHBoxLayout()
        button_row.addWidget(self.select_button)
        button_row.addWidget(self.paste_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self.drop_area)
        layout.addLayout(button_row)
        layout.addWidget(self.progress_row)
        layout.addWidget(self.result_table, stretch=1)
        layout.addWidget(self.bottom_bar)
