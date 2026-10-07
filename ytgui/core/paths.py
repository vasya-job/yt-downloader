"""Поиск yt-dlp/ffmpeg и подбор свободного имени файла."""
from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

# GUI-приложение, запущенное из Finder, не видит Homebrew в PATH.
SYSTEM_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def bundled_dir() -> str:
    """Папка с yt-dlp/ffmpeg: внутри .app или packaging/bin при разработке."""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parents[1] / "Resources" / "bin")
    return str(Path(__file__).resolve().parents[2] / "packaging" / "bin")


def _executable(directory: str, name: str) -> str | None:
    candidate = os.path.join(directory, name)
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def find_tool(name: str, extra_dirs: Sequence[str] | None = None) -> str | None:
    dirs = extra_dirs if extra_dirs is not None else [bundled_dir()]
    for directory in dirs:
        found = _executable(directory, name)
        if found:
            return found
    on_path = shutil.which(name)
    if on_path:
        return on_path
    for directory in SYSTEM_DIRS:
        found = _executable(directory, name)
        if found:
            return found
    return None


def unique_stem(folder: str, stem: str, ext: str) -> str:
    """Имя без расширения, при котором `folder/<имя>.<ext>` ещё не существует: `Song`, `Song (1)`, …"""
    candidate = stem
    number = 0
    while os.path.exists(os.path.join(folder, f"{candidate}.{ext}")):
        number += 1
        candidate = f"{stem} ({number})"
    return candidate
