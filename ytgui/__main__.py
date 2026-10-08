"""Точка входа: `python -m ytgui`."""
from __future__ import annotations

import sys


def create_app(argv: list[str]):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("YT Загрузчик")
    # Нативный стиль macOS рисует выпадающий список поверх поля и сжимает поля формы;
    # Fusion открывает список под полем и растягивает поля на всю ширину.
    app.setStyle("Fusion")
    return app


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

    from ytgui.ui.main_window import MainWindow

    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
