"""Поток-обёртка над DownloadJob: ядро не знает про Qt, Qt не знает про subprocess."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ytgui.core.events import JobResult


class DownloadWorker(QThread):
    event = Signal(object)  # ProgressEvent
    done = Signal(object)   # JobResult

    def __init__(self, options, job_factory=None) -> None:
        super().__init__()
        if job_factory is None:
            from ytgui.core.runner import DownloadJob as job_factory
        self._job = job_factory(options, self.event.emit)

    def cancel(self) -> None:
        self._job.cancel()

    def run(self) -> None:
        try:
            result = self._job.run()
        except Exception as exc:  # окно не должно навсегда остаться в состоянии «идёт загрузка»
            result = JobResult("error", f"Внутренняя ошибка: {exc}")
        self.done.emit(result)
