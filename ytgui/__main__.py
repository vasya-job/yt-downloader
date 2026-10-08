"""Точка входа: `python -m ytgui`."""
from __future__ import annotations

import sys


def main() -> int:
    if "--version" in sys.argv:
        from ytgui import __version__

        print(f"YT Загрузчик {__version__}")
        return 0

    if "--self-check" in sys.argv:
        from ytgui.core.paths import find_tool

        print("yt-dlp:", find_tool("yt-dlp"))
        print("ffmpeg:", find_tool("ffmpeg"))
        return 0

    from PySide6.QtWidgets import QApplication

    from ytgui.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("YT Загрузчик")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
