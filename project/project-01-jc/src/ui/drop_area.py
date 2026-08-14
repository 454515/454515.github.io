"""Central drag-and-drop area: receives dropped images/folders (stage 5).

Highlight feedback on drag-enter (spec-05 §5): border + hint text change
colour while an external drag is hovering, restored on leave/drop.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_STYLE_NORMAL = (
    "#dropArea { border: 2px dashed #999; border-radius: 8px;"
    " background: #fafafa; }"
)
_STYLE_HIGHLIGHT = (
    "#dropArea { border: 2px dashed #2a9d8f; border-radius: 8px;"
    " background: #e8f7f5; }"
)


class DropArea(QWidget):
    dropped_paths = Signal(list)  # list[str]: mixed files and/or folders

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.is_highlighted = False
        self.setMinimumHeight(160)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setStyleSheet(_STYLE_NORMAL)

        self._title = QLabel("拖拽图片到此处开始识别")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setObjectName("dropTitle")
        self._title.setStyleSheet("font-size: 16px; color: #333;")
        hint = QLabel("（支持微信拖拽/文件/文件夹/粘贴）")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("dropHint")
        hint.setStyleSheet("color: #888;")

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(self._title)
        layout.addWidget(hint)
        layout.addStretch(1)

    # ---- drag & drop ----
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_highlight(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 (Qt name)
        self._set_highlight(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_highlight(False)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped_paths.emit(paths)
        event.acceptProposedAction()

    def _set_highlight(self, on: bool) -> None:
        self.is_highlighted = on
        self.setStyleSheet(_STYLE_HIGHLIGHT if on else _STYLE_NORMAL)
        colour = "#2a9d8f" if on else "#333"
        self._title.setText("释放即可识别" if on else "拖拽图片到此处开始识别")
        self._title.setStyleSheet(f"font-size: 16px; color: {colour};")
