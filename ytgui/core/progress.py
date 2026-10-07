"""Разбор строк stdout yt-dlp и форматирование размеров."""
from __future__ import annotations

import math
import re

from ytgui.core.command import PROGRESS_PREFIX
from ytgui.core.events import ProgressEvent

_ITEM_RE = re.compile(r"^\[download\] Downloading (?:item|video) (\d+) of (\d+)")
_SKIPPED_RE = re.compile(r"^\[download\] (.+) has already been downloaded")
_STAGES = (
    ("[ExtractAudio]", "Конвертация аудио…"),
    ("[Merger]", "Объединение видео и аудио…"),
    ("[VideoConvertor]", "Конвертация видео…"),
    ("[VideoRemuxer]", "Упаковка видео…"),
    ("[Fixup", "Исправление контейнера…"),
)


def _number(raw: str) -> float | None:
    try:
        value = float(raw)
        if math.isfinite(value) and value >= 0:
            return value
        return None
    except (ValueError, OverflowError):
        return None


def _parse_progress(line: str) -> ProgressEvent:
    parts = line.split("|")
    if len(parts) < 7:
        return ProgressEvent("line", text=line)
    downloaded = _number(parts[2])
    total = _number(parts[3]) or _number(parts[4])
    speed = _number(parts[5])
    eta = _number(parts[6])
    percent = None
    if downloaded is not None and total:
        percent = min(100.0, downloaded / total * 100)
    return ProgressEvent(
        "download",
        text=parts[1],
        percent=percent,
        downloaded=int(downloaded) if downloaded is not None else None,
        total=int(total) if total else None,
        speed=speed,
        eta=int(eta) if eta is not None else None,
    )


def parse_line(line: str) -> ProgressEvent:
    line = line.rstrip("\r\n")
    if line.startswith(PROGRESS_PREFIX):
        return _parse_progress(line)
    match = _ITEM_RE.match(line)
    if match:
        return ProgressEvent(
            "item", text=line, item_index=int(match[1]), item_count=int(match[2])
        )
    match = _SKIPPED_RE.match(line)
    if match:
        return ProgressEvent("skipped", text=match[1])
    for prefix, text in _STAGES:
        if line.startswith(prefix):
            return ProgressEvent("stage", text=text)
    return ProgressEvent("line", text=line)


def format_bytes(n: float) -> str:
    units = ("Б", "КБ", "МБ", "ГБ")
    value = float(n)
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        return f"{int(value)} Б"
    return f"{value:.1f}".replace(".", ",") + f" {units[index]}"


def describe_download(ev: ProgressEvent) -> str:
    if ev.downloaded is None:
        return ""
    text = format_bytes(ev.downloaded)
    if ev.total:
        text += f" из {format_bytes(ev.total)}"
    if ev.speed:
        text += f" ({format_bytes(ev.speed)}/с)"
    return text
