"""Results table widget: per-document-type columns (spec-04 §4.5, spec-06 §5).

The column headers are parameterized (idcard: 序号/姓名/性别/身份证号; invoice:
序号/姓名/发票代码/发票号码/金额/开票时间) with the default being the idcard set.

Interaction (stage-7 supplement 2): a left-click on any editable cell opens
the editor immediately and selects the whole text — so the user can drag-select
text inside the cell right away, no double-click needed. Ctrl+C inside the
editor copies through put_excel_clipboard (HTML mso-number-format + TSV) so
the 18-digit 身份证号 pastes into Excel as text, never as scientific notation.
"""
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLineEdit,
    QMenu,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

import src.config as cfg

from src.ui.clipboard import put_excel_clipboard

COLUMNS = cfg.ID_CARD_COLUMNS


class _CopySafeTextDelegate(QStyledItemDelegate):
    """Standard text editor whose Ctrl+C also writes the Excel-safe flavours."""

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.KeyPress
                and event.key() == Qt.Key_C
                and (event.modifiers() & Qt.ControlModifier)
                and isinstance(obj, QLineEdit)):
            text = obj.selectedText()
            if text:  # paste the selected text with Excel's text format
                put_excel_clipboard([[text]])
                return True  # swallow the default plain-text copy
        return super().eventFilter(obj, event)


class ResultTable(QTableWidget):
    delete_requested = Signal()
    copy_selected_requested = Signal()

    def __init__(self, columns: list[str] | None = None,
                 parent: QWidget | None = None) -> None:
        self._columns = list(columns) if columns is not None else list(COLUMNS)
        super().__init__(0, len(self._columns), parent)
        self.setHorizontalHeaderLabels(self._columns)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Double-click / F2 still edit; a plain left-click also edits (below).
        self.setEditTriggers(QAbstractItemView.DoubleClicked
                             | QAbstractItemView.EditKeyPressed)
        self.setItemDelegate(_CopySafeTextDelegate(self))
        # Cell-level selection stays available (delete/region-copy operate on
        # selected indexes); single-click usually enters the editor instead.
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def mousePressEvent(self, event) -> None:
        """Left-click an editable cell -> open the editor with all text selected
        (drag-select works immediately); right-click closes any open editor so
        the table's own context menu (delete) appears, not the editor's."""
        if event.button() == Qt.RightButton:
            editor = self.indexWidget(self.currentIndex())
            if editor is not None:
                self.commitData(editor)
                self.closeEditor(editor, QStyledItemDelegate.NoHint)
            super().mousePressEvent(event)
            return
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if item is not None and item.flags() & Qt.ItemIsEditable:
                QTimer.singleShot(0, lambda: self._open_editor(item.row(),
                                                               item.column()))
                return
        super().mousePressEvent(event)

    def _open_editor(self, r: int, c: int) -> None:
        item = self.item(r, c)
        if item is None:
            return
        self.setCurrentItem(item)
        self.editItem(item)
        editor = self.indexWidget(self.currentIndex())
        if isinstance(editor, QLineEdit):
            editor.selectAll()

    def set_rows(self, rows: list[list[str]]) -> None:
        """Replace all rows; each row is a list of cell strings."""
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self._fill_row(r, row)

    def append_row(self, cells: list[str]) -> None:
        """Append one row; the 序号 column is kept non-editable."""
        r = self.rowCount()
        self.insertRow(r)
        self._fill_row(r, cells)

    def rows_data(self) -> list[list[str]]:
        """All rows including the header (for copy-all)."""
        return [self._columns] + [self._row_text(r) for r in range(self.rowCount())]

    def selected_cells_data(self) -> list[list[str]]:
        """Selected cells as a grid (its column headers first), or [] if
        nothing is selected. Any rectangular selection — one cell, a row, a
        region across rows — comes back with the same shape it was picked."""
        indexes = self.selectedIndexes()
        if not indexes:
            return []
        rows = sorted({i.row() for i in indexes})
        cols = sorted({i.column() for i in indexes})
        grid = [[self.item(r, c).text() if self.item(r, c) else ""
                 for c in cols] for r in rows]
        return [[self._columns[c] for c in cols]] + grid

    def renumber(self) -> None:
        """Re-number the first column starting from 1."""
        for r in range(self.rowCount()):
            item = self.item(r, 0)
            if item:
                item.setText(str(r + 1))

    # ---- internals ----

    def _fill_row(self, r: int, row: list[str]) -> None:
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if c == 0:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.setItem(r, c, item)

    def _row_text(self, r: int) -> list[str]:
        return [self.item(r, c).text() if self.item(r, c) else ""
                for c in range(len(self._columns))]

    def _show_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("删除选中行", self.delete_requested.emit)
        menu.addAction("复制选中区域", self.copy_selected_requested.emit)
        menu.exec(self.viewport().mapToGlobal(pos))
