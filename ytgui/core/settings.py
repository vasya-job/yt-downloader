"""Настройки программы в JSON. Битый или чужой файл не должен ронять запуск."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ytgui.core.options import (
    AUDIO_FORMATS,
    COOKIE_BROWSERS,
    DEFAULT_TEMPLATE,
    HEIGHT_LIMITS,
    VIDEO_FORMATS,
)

APP_DIR_NAME = "YT Загрузчик"


@dataclass
class Settings:
    folder: str = ""
    mode: str = "audio"
    audio_format: str = "mp3"
    audio_quality: int = 0
    video_format: str = "mp4"
    max_height: int | None = None
    template: str = DEFAULT_TEMPLATE
    cookies_browser: str | None = None
    open_folder: bool = True


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


_VALID = {
    "folder": lambda v: isinstance(v, str),
    "mode": lambda v: v in ("audio", "video"),
    "audio_format": lambda v: v in AUDIO_FORMATS,
    "audio_quality": lambda v: _is_int(v) and 0 <= v <= 9,
    "video_format": lambda v: v in VIDEO_FORMATS,
    "max_height": lambda v: v in HEIGHT_LIMITS,
    "template": lambda v: isinstance(v, str) and bool(v.strip()),
    "cookies_browser": lambda v: v in COOKIE_BROWSERS,
    "open_folder": lambda v: isinstance(v, bool),
}


def settings_path() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_DIR_NAME / "settings.json"


def load(path: str | Path | None = None) -> Settings:
    target = Path(path) if path else settings_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(raw, dict):
        return Settings()
    values = {}
    for field in fields(Settings):
        if field.name in raw and _VALID[field.name](raw[field.name]):
            values[field.name] = raw[field.name]
    return Settings(**values)


def save(settings: Settings, path: str | Path | None = None) -> None:
    target = Path(path) if path else settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)
