"""Перевод ошибок yt-dlp в короткие понятные сообщения."""
from __future__ import annotations

import re
from collections.abc import Iterable

FFMPEG_MISSING = "Не найден ffmpeg. Установите его командой `brew install ffmpeg` и повторите."
YTDLP_MISSING = "Не найден yt-dlp. Установите его командой `brew install yt-dlp` и повторите."

_COOKIES_HINT = "Выберите в поле cookies браузер, где вы вошли в YouTube, и повторите."

_RULES = (
    (r"not a bot", f"YouTube просит подтвердить, что вы не бот. {_COOKIES_HINT}"),
    (r"private video", f"Это приватное видео, доступ закрыт. {_COOKIES_HINT}"),
    (
        r"confirm your age|age-restricted|inappropriate for some users",
        f"Видео с ограничением по возрасту. {_COOKIES_HINT}",
    ),
    (
        r"video unavailable|this video is unavailable|has been removed|blocked it in your country|not available in your country",
        "Видео недоступно: удалено, скрыто или закрыто в вашем регионе.",
    ),
    (
        r"requested format is not available",
        "У этого видео нет выбранного формата или качества. Попробуйте другой формат.",
    ),
    (r"unsupported url", "Эта ссылка не поддерживается."),
    (r"ffprobe and ffmpeg not found|ffmpeg not found|ffmpeg is not installed", FFMPEG_MISSING),
    (
        r"cookies database|failed to decrypt|keyring|could not copy .*cookie",
        "Не удалось прочитать cookies браузера. Закройте браузер или выберите другой.",
    ),
    (
        r"http error (403|429)",
        "YouTube отказал в доступе или временно ограничил запросы (HTTP 403/429). Подождите немного и повторите, либо выберите браузер в поле cookies.",
    ),
    (
        r"getaddrinfo|nodename nor servname|urlopen error|temporary failure|timed out|network is unreachable|connection reset|ssl:|certificate verify|http error 5",
        "Нет связи с YouTube. Проверьте интернет и повторите.",
    ),
)
_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), text) for pattern, text in _RULES)
_ID_PREFIX = re.compile(r"^\[[^\]]+\]\s+[\w-]+:\s+")
_MAX_LEN = 300


def explain(lines: Iterable[str], exit_code: int | None = None) -> str:
    errors = [line for line in lines if line.startswith("ERROR:")]
    if not errors:
        code = f" (код {exit_code})" if exit_code is not None else ""
        return f"Загрузка не удалась{code}. Подробности в логе."
    last = errors[-1]
    for pattern, text in _COMPILED:
        if pattern.search(last):
            return text
    message = _ID_PREFIX.sub("", last[len("ERROR:"):].strip())
    if len(message) > _MAX_LEN:
        message = message[: _MAX_LEN - 1] + "…"
    return message
