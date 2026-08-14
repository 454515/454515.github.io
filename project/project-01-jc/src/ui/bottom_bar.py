"""Bottom action bar: count label + 复制全部 / 清空 buttons (spec-04 §4.6)."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class BottomBar(QWidget):
    """Shows result count and hosts the copy-all / clear actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.count_label = QLabel("共 0 条结果")
        self.copy_button = QPushButton("复制全部")
        self.clear_button = QPushButton("清空")

        layout = QHBoxLayout(self)
        layout.addWidget(self.count_label)
        layout.addStretch(1)
        layout.addWidget(self.copy_button)
        layout.addWidget(self.clear_button)
        layout.setContentsMargins(0, 0, 0, 0)

    def set_count(self, count: int) -> None:
        self.count_label.setText(f"共 {count} 条结果")
