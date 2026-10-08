"""Готовые шаблоны имени файла и пример результата. Модуль не зависит от Qt."""
from __future__ import annotations

import re
from datetime import date

from ytgui.core.command import playlist_template
from ytgui.core.options import DEFAULT_TEMPLATE

PRESETS: tuple[tuple[str, str], ...] = (
    ("Название", "%(title)s.%(ext)s"),
    ("Автор — Название", "%(uploader)s - %(title)s.%(ext)s"),
    ("Название [код видео]", "%(title)s [%(id)s].%(ext)s"),
    ("Дата — Название", "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"),
)
CUSTOM_LABEL = "Свой шаблон…"

_SAMPLE_DATE = date(2026, 10, 8)
_SAMPLES: dict[str, str] = {
    "title": "Название ролика",
    "uploader": "Автор канала",
    "id": "dQw4w9WgXcQ",
    "upload_date": _SAMPLE_DATE.strftime("%Y%m%d"),
    "playlist_index": "03",
}
_NUMERIC_CONVERSIONS = "dioxXeEfFgG"
# `%%` или поле `%(имя)` с необязательным форматом (`s`, `03d`, `.30s`).
_TOKEN = re.compile(r"%%|%\((?P<field>[^()]*)\)(?P<fmt>[-#0 +]*\d*(?:\.\d+)?[a-zA-Z])")


def preset_index(template: str) -> int | None:
    for index, (_label, preset) in enumerate(PRESETS):
        if preset == template:
            return index
    return None


def ensure_extension(template: str) -> str:
    template = template.strip()
    if not template:
        return DEFAULT_TEMPLATE
    if "%(ext)s" not in template:
        return template + ".%(ext)s"
    return template


def _sample_value(name: str, date_format: str | None, conversion: str, ext: str):
    """Пример значения для поля или None, если поле неизвестно или формат к нему не подходит."""
    if name == "ext":
        return ext if conversion == "s" else None
    if name == "upload_date" and date_format is not None:
        return _SAMPLE_DATE.strftime(date_format) if conversion == "s" else None
    if date_format is not None or name not in _SAMPLES:
        return None
    if conversion in _NUMERIC_CONVERSIONS:
        return int(_SAMPLES[name]) if name == "playlist_index" else None
    return _SAMPLES[name]


def _replace(match: re.Match, ext: str) -> str:
    if match.group(0) == "%%":
        return "%"
    name, _sep, date_format = match.group("field").partition(">")
    fmt = match.group("fmt")
    value = _sample_value(name, date_format if _sep else None, fmt[-1], ext)
    if value is None:
        return match.group(0)
    try:
        return ("%" + fmt) % value
    except (TypeError, ValueError):
        return match.group(0)


def preview_name(template: str, ext: str, playlist: bool = False) -> str:
    """Пример имени файла для шаблона на выдуманных данных (как его соберёт yt-dlp)."""
    if playlist:
        template = playlist_template(template)
    return _TOKEN.sub(lambda match: _replace(match, ext), template)
