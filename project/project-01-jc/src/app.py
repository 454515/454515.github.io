"""检测识别 - 程序入口.

Launches the main window. Recognition is driven by imports (drag / file
dialog / clipboard paste); the window starts empty and shows a hint.
"""
import sys
from pathlib import Path

# Make the project root importable so `python src/app.py` works.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

import src.config as cfg  # noqa: E402
from src.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    if cfg.MODELS_DIR.exists():
        window.statusBar().showMessage("拖入图片或粘贴(Ctrl+V)开始识别")
    else:
        # spec-07 §3.1: no bundled models -> fall back to default cache, hint.
        window.statusBar().showMessage("未找到 models/ 目录，将使用默认模型（可能需联网下载）")
    window.setWindowTitle("jc")
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
