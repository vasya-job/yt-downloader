"""Параметры загрузки и их проверка. Модуль не зависит от Qt."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs, urlparse

DEFAULT_TEMPLATE = "%(title)s.%(ext)s"
AUDIO_FORMATS = ("mp3", "m4a", "opus", "wav")
VIDEO_FORMATS = ("mp4", "mkv", "webm")
HEIGHT_LIMITS = (None, 1080, 720, 480)  # None = лучшее
COOKIE_BROWSERS = (None, "chrome", "firefox", "edge")


class Mode(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True)
class DownloadOptions:
    url: str
    folder: str
    mode: Mode = Mode.AUDIO
    audio_format: str = "mp3"
    audio_quality: int = 0
    video_format: str = "mp4"
    max_height: int | None = None
    template: str = DEFAULT_TEMPLATE
    cookies_browser: str | None = None
    playlist: bool = False

    @property
    def clean_url(self) -> str:
        return self.url.strip()

    @property
    def final_ext(self) -> str:
        return self.audio_format if self.mode is Mode.AUDIO else self.video_format

    def validate(self) -> None:
        parsed = urlparse(self.clean_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Вставьте ссылку, которая начинается с http:// или https://")
        if not self.folder.strip():
            raise ValueError("Выберите папку для сохранения")
        if not self.template.strip():
            raise ValueError("Шаблон имени не может быть пустым")
        if self.audio_format not in AUDIO_FORMATS:
            raise ValueError(f"Неизвестный аудиоформат: {self.audio_format}")
        if self.video_format not in VIDEO_FORMATS:
            raise ValueError(f"Неизвестный видеоформат: {self.video_format}")
        if not 0 <= self.audio_quality <= 9:
            raise ValueError("Качество аудио должно быть от 0 до 9")
        if self.max_height not in HEIGHT_LIMITS:
            raise ValueError("Неизвестное ограничение качества видео")
        if self.cookies_browser not in COOKIE_BROWSERS:
            raise ValueError("Неизвестный браузер для cookies")


def is_playlist_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if "list" in parse_qs(parsed.query):
        return True
    return parsed.path.rstrip("/") == "/playlist"
