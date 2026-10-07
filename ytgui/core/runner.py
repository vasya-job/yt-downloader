"""Запуск yt-dlp как внешнего процесса: чтение вывода, отмена, итоговый результат."""
from __future__ import annotations

import dataclasses
import os
import signal
import subprocess
import threading
from collections import deque
from collections.abc import Callable

from ytgui.core.command import PROBE_PREFIX, build_command, build_probe_command, literal_template
from ytgui.core.errors import FFMPEG_MISSING, YTDLP_MISSING, explain
from ytgui.core.events import JobResult, ProgressEvent
from ytgui.core.options import DownloadOptions
from ytgui.core.paths import SYSTEM_DIRS, bundled_dir, find_tool, unique_stem
from ytgui.core.progress import parse_line

KILL_GRACE_SECONDS = 3.0
MAX_TAIL_LINES = 400


class _Cancelled(Exception):
    pass


class _LaunchFailed(Exception):
    pass


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    dirs = [bundled_dir(), *SYSTEM_DIRS]
    if env.get("PATH"):
        dirs.append(env["PATH"])
    env["PATH"] = os.pathsep.join(dirs)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class DownloadJob:
    def __init__(
        self,
        options: DownloadOptions,
        on_event: Callable[[ProgressEvent], None],
        ytdlp: str | None = None,
        ffmpeg: str | None = None,
        find: Callable[[str], str | None] = find_tool,
        kill_grace: float = KILL_GRACE_SECONDS,
    ) -> None:
        self._options = options
        self._on_event = on_event
        self._ytdlp = ytdlp
        self._ffmpeg = ffmpeg
        self._find = find
        self._kill_grace = kill_grace
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._cancelled = False
        self._kill_timer: threading.Timer | None = None
        self._tail: deque[str] = deque(maxlen=MAX_TAIL_LINES)

    # ---- публичный интерфейс -------------------------------------------------

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            proc = self._proc
            if proc is None or self._kill_timer is not None:
                return
            timer = threading.Timer(self._kill_grace, self._force_kill, (proc,))
            timer.daemon = True
            self._kill_timer = timer
            timer.start()
        self._signal_group(proc, signal.SIGTERM)

    def run(self) -> JobResult:
        options = self._options
        try:
            options.validate()
        except ValueError as exc:
            return JobResult("error", str(exc))
        ytdlp = self._ytdlp or self._find("yt-dlp")
        if not ytdlp:
            return JobResult("error", YTDLP_MISSING)
        ffmpeg = self._ffmpeg or self._find("ffmpeg")
        if not ffmpeg:
            return JobResult("error", FFMPEG_MISSING)
        try:
            os.makedirs(options.folder, exist_ok=True)
        except OSError as exc:
            return JobResult("error", f"Не удалось создать папку: {exc.strerror or exc}")
        if not os.access(options.folder, os.W_OK):
            return JobResult("error", "Нет прав на запись в выбранную папку.")
        try:
            if self._cancelled:
                raise _Cancelled
            if not options.playlist:
                options, failure = self._with_unique_name(options, ytdlp)
                if failure:
                    return failure
            return self._download(options, ytdlp, ffmpeg)
        except _Cancelled:
            return JobResult("cancelled", "Отменено")
        except _LaunchFailed as exc:
            return JobResult("error", f"Не удалось запустить yt-dlp: {exc}")
        except Exception as exc:  # например, сбой в обработчике событий
            return JobResult("error", f"Внутренняя ошибка: {exc}")

    # ---- внутреннее ------------------------------------------------------------

    @staticmethod
    def _signal_group(proc: subprocess.Popen, sig: int) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, sig)  # процесс запущен в своей группе, убиваем вместе с ffmpeg
        except (ProcessLookupError, PermissionError):
            pass

    def _force_kill(self, proc: subprocess.Popen) -> None:
        # Без проверки poll(): группа может жить, даже если yt-dlp уже завершился (ffmpeg держит pipe).
        # Лидер не reaped, пока _stream не вызвал proc.wait(), поэтому pid не переиспользован.
        with self._lock:
            if self._proc is not proc:
                return
            self._kill_group(proc)

    @staticmethod
    def _kill_group(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def _stream(self, cmd: list[str], handle_line: Callable[[str], None]) -> int:
        with self._lock:
            if self._cancelled:
                raise _Cancelled
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    start_new_session=True,
                    env=child_env(),
                )
            except OSError as exc:
                raise _LaunchFailed(exc.strerror or str(exc)) from exc
            self._proc = proc
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\r\n")
                if line:
                    handle_line(line)
            return proc.wait()
        finally:
            with self._lock:
                timer, self._kill_timer = self._kill_timer, None
                if timer is not None:
                    timer.cancel()
                if proc.returncode is None:
                    self._kill_group(proc)  # при выходе по исключению не оставляем процесс сиротой
                    proc.wait()
                proc.stdout.close()
                self._proc = None

    def _with_unique_name(
        self, options: DownloadOptions, ytdlp: str
    ) -> tuple[DownloadOptions, JobResult | None]:
        names: list[str] = []
        lines: list[str] = []

        def handle(line: str) -> None:
            lines.append(line)
            if line.startswith(PROBE_PREFIX):
                names.append(line[len(PROBE_PREFIX):])

        self._on_event(ProgressEvent("stage", text="Проверка ссылки…"))
        code = self._stream(build_probe_command(options, ytdlp), handle)
        if self._cancelled:
            raise _Cancelled
        if code != 0 or not names:
            return options, JobResult("error", explain(lines, code), code)
        rel_dir, base = os.path.split(names[-1])
        stem = os.path.splitext(base)[0]
        unique = unique_stem(os.path.join(options.folder, rel_dir), stem, options.final_ext)
        if unique == stem:
            return options, None
        self._on_event(
            ProgressEvent("line", text=f"Файл уже есть, сохраняю как: {unique}.{options.final_ext}")
        )
        return dataclasses.replace(options, template=literal_template(rel_dir, unique)), None

    def _download(self, options: DownloadOptions, ytdlp: str, ffmpeg: str) -> JobResult:
        skipped = 0

        def handle(line: str) -> None:
            nonlocal skipped
            self._tail.append(line)
            event = parse_line(line)
            if event.kind == "skipped":
                skipped += 1
            self._on_event(event)

        code = self._stream(build_command(options, ytdlp, ffmpeg), handle)
        if self._cancelled:
            return JobResult("cancelled", "Отменено", code, skipped)
        if code == 0:
            note = f" (пропущено уже скачанных: {skipped})" if skipped else ""
            return JobResult("ok", "Готово" + note, code, skipped)
        return JobResult("error", explain(self._tail, code), code, skipped)
