"""Сборка командной строки yt-dlp. Чистые функции: процессы здесь не запускаются."""
from __future__ import annotations

import os

from ytgui.core.options import DownloadOptions, Mode

PROGRESS_PREFIX = "YTG|"
PROBE_PREFIX = "YTGFILE|"
PROGRESS_TEMPLATE = (
    "download:YTG|%(progress.status)s|%(progress.downloaded_bytes)s|"
    "%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|"
    "%(progress.speed)s|%(progress.eta)s"
)
_PLAYLIST_INDEX = "%(playlist_index)s"


def video_selector(fmt: str, max_height: int | None) -> str:
    cond = f"[height<={max_height}]" if max_height else ""
    if fmt == "webm":
        return f"bv*{cond}[ext=webm]+ba[ext=webm]/b{cond}[ext=webm]"
    if fmt == "mp4":
        return f"bv*{cond}[ext=mp4]+ba[ext=m4a]/b{cond}[ext=mp4]/bv*{cond}+ba/b{cond}"
    return f"bv*{cond}+ba/b{cond}"


def playlist_template(template: str) -> str:
    if "playlist_index" in template:
        return template
    return f"{_PLAYLIST_INDEX} - {template}"


def literal_template(rel_dir: str, stem: str) -> str:
    """Шаблон -o для уже известного имени: `%` экранируется, расширение подставит yt-dlp."""
    return os.path.join(rel_dir, stem.replace("%", "%%")) + ".%(ext)s"


def _cookies(o: DownloadOptions) -> list[str]:
    return ["--cookies-from-browser", o.cookies_browser] if o.cookies_browser else []


def build_command(o: DownloadOptions, ytdlp: str = "yt-dlp", ffmpeg: str | None = None) -> list[str]:
    cmd = [ytdlp, "--newline", "--progress-template", PROGRESS_TEMPLATE]
    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
    cmd += _cookies(o)
    cmd += ["--yes-playlist", "--no-overwrites"] if o.playlist else ["--no-playlist"]
    if o.mode is Mode.AUDIO:
        cmd += ["-x", "--audio-format", o.audio_format]
        if o.audio_format != "wav":
            cmd += ["--audio-quality", str(o.audio_quality)]
    else:
        cmd += ["-f", video_selector(o.video_format, o.max_height)]
        cmd += ["--merge-output-format", o.video_format]
    template = playlist_template(o.template) if o.playlist else o.template
    cmd += ["-P", o.folder, "-o", template, o.clean_url]
    return cmd


def build_probe_command(o: DownloadOptions, ytdlp: str = "yt-dlp") -> list[str]:
    """Команда, которая печатает будущее имя файла (`YTGFILE|<имя>`), ничего не скачивая."""
    cmd = [ytdlp, "--simulate", "--no-playlist", "--print", PROBE_PREFIX + "%(filename)s"]
    cmd += ["-o", o.template]
    cmd += _cookies(o)
    cmd.append(o.clean_url)
    return cmd
