"""Типы, которыми ядро сообщает о ходе загрузки."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EventKind = Literal["download", "item", "stage", "skipped", "line"]
JobStatus = Literal["ok", "error", "cancelled"]


@dataclass(frozen=True)
class ProgressEvent:
    kind: EventKind
    text: str = ""
    percent: float | None = None
    downloaded: int | None = None
    total: int | None = None
    speed: float | None = None
    eta: int | None = None
    item_index: int | None = None
    item_count: int | None = None


@dataclass(frozen=True)
class JobResult:
    status: JobStatus
    message: str
    exit_code: int | None = None
    skipped: int = 0
