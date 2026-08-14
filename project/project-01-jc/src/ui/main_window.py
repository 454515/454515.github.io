"""Main application window. See spec-04 §4, spec-05 §4, spec-06 §4.

Thin shell that hosts one RecognitionPage per document type:
- 身份证识别 tab: IDCardProcessor + card preprocess pipeline
- 发票识别 tab: InvoiceProcessor + light document preprocess (invoices are
  full-page; the card pipeline warps them, so it is skipped — see
  preprocess_document)

Engine warmup runs on a background daemon thread so the window appears fast;
pages trigger it (idempotently) before their first batch. Global Ctrl+C /
Ctrl+V shortcuts dispatch to whichever tab is active.
"""
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QTabWidget

import src.config as cfg
from src.ocr.engine import get_engine
from src.processors import IDCardProcessor, InvoiceProcessor, get_processor
from src.ui.recognition_page import RecognitionPage
from src.utils.preprocess import preprocess_document, preprocess_image


class MainWindow(QMainWindow):
    """Main window for 检测识别."""

    recognition_finished = Signal(int)  # failed count (idcard page; test hook)

    def __init__(self, engine=None, processor=None) -> None:
        super().__init__()
        self.setWindowTitle("检测识别")
        self.resize(760, 560)

        self._engine = engine if engine is not None else get_engine()
        idcard_processor = (processor if processor is not None
                            else get_processor("idcard"))
        self._engine_ready = False
        self._warming_up = False
        # Defer model warmup by 200ms so the window appears before the heavy
        # PaddleOCR init blocks the event loop (~3-7s cold load).
        QTimer.singleShot(200, self._warmup_engine)

        tabs = QTabWidget()
        self._idcard_page = RecognitionPage(
            cfg.ID_CARD_COLUMNS, cfg.ID_CARD_FIELDS, idcard_processor,
            preprocess_image, self._engine, warmup=self._warmup_engine)
        self._invoice_page = RecognitionPage(
            cfg.INVOICE_COLUMNS, cfg.INVOICE_FIELDS, InvoiceProcessor(),
            preprocess_document, self._engine, warmup=self._warmup_engine)
        tabs.addTab(self._idcard_page, "身份证识别")
        tabs.addTab(self._invoice_page, "发票识别")
        self._tabs = tabs
        self.setCentralWidget(tabs)

        # Test-compat aliases: existing tests reach the idcard page's widgets
        # and result actions through the window (pre-page-refactor API).
        self.result_table = self._idcard_page.result_table
        self.bottom_bar = self._idcard_page.bottom_bar
        self.progress_bar = self._idcard_page.progress_bar
        self.progress_label = self._idcard_page.progress_label
        self.progress_row = self._idcard_page.progress_row
        self.drop_area = self._idcard_page.drop_area
        self.select_button = self._idcard_page.select_button
        self.paste_button = self._idcard_page.paste_button

        # Global shortcuts dispatch to the active tab's page (an
        # ApplicationShortcut on every page would fire twice).
        QShortcut(QKeySequence.Paste, self, activated=self._dispatch_paste,
                  context=Qt.ApplicationShortcut)
        QShortcut(QKeySequence.Copy, self, activated=self._dispatch_copy,
                  context=Qt.ApplicationShortcut)
        self._idcard_page.recognition_finished.connect(self.recognition_finished)

    def closeEvent(self, event) -> None:
        self._idcard_page.stop_and_cleanup()
        self._invoice_page.stop_and_cleanup()
        super().closeEvent(event)

    # ---- global shortcut dispatch (active tab) ----

    def _active_page(self) -> RecognitionPage:
        return self._tabs.currentWidget()

    def _dispatch_paste(self) -> None:
        page = self._active_page()
        if page is not None:
            page._paste_clipboard()

    def _dispatch_copy(self) -> None:
        page = self._active_page()
        if page is not None:
            page._copy_selected()

    # ---- engine warmup (shared by both pages) ----

    def _warmup_engine(self) -> None:
        """Load the model on a background daemon thread (idempotent)."""
        if self._engine_ready or self._warming_up:
            return
        self._warming_up = True

        def _do() -> None:
            try:
                warmup = getattr(self._engine, "warmup", None)
                if callable(warmup):
                    warmup()
                self._engine_ready = True
            except Exception:  # noqa: BLE001 - keep the app alive on load failure
                self._engine_ready = False
            finally:
                self._warming_up = False

        threading.Thread(target=_do, daemon=True).start()

    # ---- test-compat delegators -> idcard page ----

    def _import_paths(self, paths: list[str]) -> None:
        self._idcard_page._import_paths(paths)

    def _paste_clipboard(self) -> None:
        self._idcard_page._paste_clipboard()

    def _copy_all(self) -> None:
        self._idcard_page._copy_all()

    def _copy_selected(self) -> None:
        self._idcard_page._copy_selected()

    def _delete_selected(self) -> None:
        self._idcard_page._delete_selected()

    def _do_clear(self) -> None:
        self._idcard_page._do_clear()

    def add_demo_rows(self, rows: list) -> None:
        self._idcard_page.add_demo_rows(rows)
