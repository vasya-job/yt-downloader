# YT Загрузчик: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Однооконная macOS-программа на PySide6, которая скачивает аудио и видео через yt-dlp с прогрессом в том же окне.

**Architecture:** Ядро `ytgui/core` на чистом Python (без Qt) собирает команду yt-dlp, запускает её через `subprocess`, разбирает stdout и сообщает о событиях колбэками. Окно `ytgui/ui` оборачивает `DownloadJob` в `QThread`. Настройки хранятся в JSON. Упаковка в `.app` через PyInstaller, yt-dlp и ffmpeg кладутся в `Contents/Resources/bin`.

**Tech Stack:** Python 3.11 (venv `.venv`), PySide6 6.11, pytest, PyInstaller; внешние `yt-dlp` и `ffmpeg`.

**Spec:** `docs/superpowers/specs/2026-10-07-yt-downloader-design.md`

## Global Constraints

- Платформа только macOS. Python 3.11 из `/opt/homebrew/bin/python3.11` (PySide6 не ставится на системный Python 3.14).
- Пакеты `ytgui/core/*` не импортируют Qt. Всё Qt-зависимое лежит в `ytgui/ui/*`.
- Интерфейс и сообщения на русском, с корректной орфографией. Заголовок окна: `YouTube Загрузчик`.
- Окно: фиксированная ширина 680 px, высота по содержимому; без вкладок и мастеров.
- Шаблон имени по умолчанию: `%(title)s.%(ext)s`. Форматы аудио: mp3, m4a, opus, wav. Форматы видео: mp4, mkv, webm. Потолок высоты: лучшее (None), 1080, 720, 480. Качество аудио 0–9, где 0 = лучшее. Браузер cookies: нет, chrome, firefox, edge.
- Настройки: `~/Library/Application Support/YT Загрузчик/settings.json`.
- Юнит-тесты не ходят в сеть и не пишут вне `tmp_path`. Сетевые проверки только в `tests/e2e` с `YTGUI_E2E=1`; скачанные файлы только в `tmp_path`/scratchpad, не в проект.
- Тесты запускаются так: `.venv/bin/python -m pytest <путь> -v` из корня проекта.
- Каждый коммит заканчивается трейлером: `-m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"` (вторым `-m`).
- Копии на диск `base` (disky-backup) не делать без просьбы пользователя.

## Review Focus

Входные данные, о которых спек молчит, но которые вероятнее всего сломают программу. Для каждого есть тест в указанной задаче.

1. Ссылка вида `watch?v=…&list=…` при выключенном чекбоксе плейлиста: должно скачаться одно видео, а не весь плейлист (Task 2).
2. Название с `%`, `[ ]` или кириллицей, когда файл уже существует: суффикс ` (1)` должен попасть в шаблон без поломки форматирования yt-dlp, `%` экранируется как `%%` (Task 2, Task 7).
3. Битый, пустой или чужой `settings.json`, а также недоступная для записи папка настроек: запуск с умолчаниями, без падения (Task 6, Task 8).
4. «Отмена» до старта процесса, дважды подряд, после завершения и закрытие окна посреди загрузки: без зависания и без падения (Task 7, Task 8).
5. Папка не существует, недоступна для записи, содержит пробелы и кириллицу; yt-dlp не найден или не запускается (Task 7).

Дополнительно, в тестах своих задач: значения `NA` в строках прогресса (Task 3) и шумные предупреждения yt-dlp с трейсбекоподобным текстом (Task 4).

## Параллельное выполнение (волны)

Правило пользователя: независимые части делают разные агенты одновременно. Файлы в волнах не пересекаются.

| Волна | Задачи | Зависит от |
|---|---|---|
| 1 | Task 1 | – |
| 2 | Task 2, 3, 4, 5, 6 (пять агентов параллельно) | Task 1 |
| 3 | Task 7 (runner), Task 8 (окно) параллельно | волна 2 |
| 4 | Task 9 (e2e), Task 10 (упаковка) параллельно | волна 3 |

Порядок для параллельных агентов: каждый работает в своём git worktree (`isolation: "worktree"`), в worktree делает `ln -s <корень основного репо>/.venv .venv`, после волны ветки сливаются в `main`. Конфликтов быть не должно: каждая задача создаёт собственные файлы.

Задача 8 не импортирует `ytgui.core.runner` на уровне модуля (ленивый импорт в `DownloadWorker`), поэтому может идти параллельно с задачей 7.

---

### Task 1: Каркас проекта и параметры загрузки

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`
- Create: `ytgui/__init__.py`, `ytgui/core/__init__.py`, `ytgui/ui/__init__.py`
- Create: `ytgui/core/options.py`
- Create: `tests/conftest.py`, `tests/test_options.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces (`ytgui/core/options.py`), на них опираются все остальные задачи:
  - константы `DEFAULT_TEMPLATE: str`, `AUDIO_FORMATS: tuple[str, ...]`, `VIDEO_FORMATS: tuple[str, ...]`, `HEIGHT_LIMITS: tuple[int | None, ...]`, `COOKIE_BROWSERS: tuple[str | None, ...]`
  - `class Mode(str, Enum)`: `AUDIO = "audio"`, `VIDEO = "video"`
  - `@dataclass(frozen=True) class DownloadOptions(url, folder, mode=Mode.AUDIO, audio_format="mp3", audio_quality=0, video_format="mp4", max_height=None, template=DEFAULT_TEMPLATE, cookies_browser=None, playlist=False)` со свойствами `clean_url -> str`, `final_ext -> str` и методом `validate() -> None` (бросает `ValueError` с русским текстом)
  - `is_playlist_url(url: str) -> bool`

- [ ] **Step 1: Создать окружение и файлы зависимостей**

`requirements.txt`:
```
PySide6>=6.9
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8
pyinstaller>=6
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

В `.gitignore` заменить строку `.venv/` на `.venv` (чтобы игнорировался и симлинк в worktree).

Run:
```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
.venv/bin/python -c "import PySide6, pytest; print(PySide6.__version__)"
```
Expected: печатается версия PySide6 (6.11.x).

- [ ] **Step 2: Создать пакеты и conftest**

`ytgui/__init__.py`, `ytgui/core/__init__.py`, `ytgui/ui/__init__.py`: пустые файлы.

`tests/conftest.py`:
```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

- [ ] **Step 3: Написать падающие тесты**

`tests/test_options.py`:
```python
import pytest

from ytgui.core.options import DownloadOptions, Mode, is_playlist_url


def make(**kw):
    base = dict(url="https://youtu.be/abc", folder="/tmp/out")
    base.update(kw)
    return DownloadOptions(**base)


def test_valid_options_pass():
    make().validate()


def test_clean_url_strips_spaces():
    assert make(url="  https://youtu.be/abc \n").clean_url == "https://youtu.be/abc"


@pytest.mark.parametrize("url", ["", "   ", "youtube.com/watch?v=1", "ftp://x.org/a", "https://"])
def test_bad_url_rejected(url):
    with pytest.raises(ValueError, match="ссылк"):
        make(url=url).validate()


def test_empty_folder_rejected():
    with pytest.raises(ValueError, match="папк"):
        make(folder="  ").validate()


def test_empty_template_rejected():
    with pytest.raises(ValueError, match="Шаблон"):
        make(template=" ").validate()


@pytest.mark.parametrize(
    "kw",
    [
        {"audio_format": "flac"},
        {"video_format": "avi"},
        {"audio_quality": 10},
        {"audio_quality": -1},
        {"max_height": 360},
        {"cookies_browser": "safari"},
    ],
)
def test_unknown_values_rejected(kw):
    with pytest.raises(ValueError):
        make(**kw).validate()


def test_final_ext_follows_mode():
    assert make(mode=Mode.AUDIO, audio_format="opus").final_ext == "opus"
    assert make(mode=Mode.VIDEO, video_format="mkv").final_ext == "mkv"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc", False),
        ("https://www.youtube.com/watch?v=abc&list=PL123", True),
        ("https://www.youtube.com/playlist?list=PL123", True),
        ("https://youtu.be/abc?list=PL123", True),
        ("https://www.youtube.com/shorts/abc", False),
        ("  https://www.youtube.com/playlist?list=PL1  ", True),
        ("", False),
        ("не ссылка", False),
    ],
)
def test_is_playlist_url(url, expected):
    assert is_playlist_url(url) is expected
```

- [ ] **Step 4: Запустить тесты, убедиться что падают**

Run: `.venv/bin/python -m pytest tests/test_options.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.options'`.

- [ ] **Step 5: Реализовать `ytgui/core/options.py`**

```python
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
```

- [ ] **Step 6: Запустить тесты, убедиться что проходят**

Run: `.venv/bin/python -m pytest tests/test_options.py -v`
Expected: все PASS.

- [ ] **Step 7: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt pyproject.toml ytgui tests
git commit -m "feat: project scaffold and download options" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Сборка команды yt-dlp

**Files:**
- Create: `ytgui/core/command.py`
- Test: `tests/test_command.py`

**Interfaces:**
- Consumes: `DownloadOptions`, `Mode` из `ytgui.core.options`.
- Produces (`ytgui/core/command.py`):
  - константы `PROGRESS_PREFIX = "YTG|"`, `PROBE_PREFIX = "YTGFILE|"`, `PROGRESS_TEMPLATE: str`
  - `video_selector(fmt: str, max_height: int | None) -> str`
  - `playlist_template(template: str) -> str`
  - `literal_template(rel_dir: str, stem: str) -> str`
  - `build_command(o: DownloadOptions, ytdlp: str = "yt-dlp", ffmpeg: str | None = None) -> list[str]`
  - `build_probe_command(o: DownloadOptions, ytdlp: str = "yt-dlp") -> list[str]`

- [ ] **Step 1: Написать падающие тесты**

`tests/test_command.py`:
```python
from ytgui.core.command import (
    PROBE_PREFIX,
    PROGRESS_TEMPLATE,
    build_command,
    build_probe_command,
    literal_template,
    playlist_template,
    video_selector,
)
from ytgui.core.options import DownloadOptions, Mode


def make(**kw):
    base = dict(url="https://youtu.be/abc", folder="/tmp/out")
    base.update(kw)
    return DownloadOptions(**base)


def test_audio_mp3_command_is_exact():
    cmd = build_command(make(audio_format="mp3", audio_quality=2))
    assert cmd == [
        "yt-dlp", "--newline", "--progress-template", PROGRESS_TEMPLATE,
        "--no-playlist",
        "-x", "--audio-format", "mp3", "--audio-quality", "2",
        "-P", "/tmp/out", "-o", "%(title)s.%(ext)s",
        "https://youtu.be/abc",
    ]


def test_wav_has_no_audio_quality():
    cmd = build_command(make(audio_format="wav"))
    assert "--audio-quality" not in cmd
    assert cmd[cmd.index("--audio-format") + 1] == "wav"


def test_video_mp4_1080_command():
    cmd = build_command(make(mode=Mode.VIDEO, video_format="mp4", max_height=1080))
    sel = cmd[cmd.index("-f") + 1]
    assert sel == (
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]"
        "/bv*[height<=1080]+ba/b[height<=1080]"
    )
    assert cmd[cmd.index("--merge-output-format") + 1] == "mp4"
    assert "-x" not in cmd


def test_video_selectors():
    assert video_selector("mp4", None) == "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
    assert video_selector("mkv", 720) == "bv*[height<=720]+ba/b[height<=720]"
    assert video_selector("webm", 480) == "bv*[height<=480][ext=webm]+ba[ext=webm]/b[height<=480][ext=webm]"


def test_playlist_flags_and_template():
    cmd = build_command(make(playlist=True))
    assert "--yes-playlist" in cmd and "--no-overwrites" in cmd
    assert "--no-playlist" not in cmd
    assert cmd[cmd.index("-o") + 1] == "%(playlist_index)s - %(title)s.%(ext)s"


def test_playlist_template_keeps_existing_index():
    t = "%(playlist_index)03d_%(title)s.%(ext)s"
    assert playlist_template(t) == t


def test_url_with_list_but_playlist_off_downloads_single_video():
    url = "https://www.youtube.com/watch?v=abc&list=PLxyz"
    cmd = build_command(make(url=url, playlist=False))
    assert "--no-playlist" in cmd and "--yes-playlist" not in cmd
    assert cmd[-1] == url


def test_cookies_and_ffmpeg_location():
    cmd = build_command(make(cookies_browser="chrome"), ytdlp="/x/yt-dlp", ffmpeg="/x/ffmpeg")
    assert cmd[0] == "/x/yt-dlp"
    assert cmd[cmd.index("--cookies-from-browser") + 1] == "chrome"
    assert cmd[cmd.index("--ffmpeg-location") + 1] == "/x/ffmpeg"


def test_url_is_stripped():
    assert build_command(make(url="  https://youtu.be/abc \n"))[-1] == "https://youtu.be/abc"


def test_probe_command():
    cmd = build_probe_command(make(cookies_browser="firefox", template="%(title)s [%(id)s].%(ext)s"))
    assert cmd[:2] == ["yt-dlp", "--simulate"]
    assert "--no-playlist" in cmd
    assert cmd[cmd.index("--print") + 1] == PROBE_PREFIX + "%(filename)s"
    assert cmd[cmd.index("-o") + 1] == "%(title)s [%(id)s].%(ext)s"
    assert "-P" not in cmd
    assert cmd[cmd.index("--cookies-from-browser") + 1] == "firefox"
    assert cmd[-1] == "https://youtu.be/abc"


def test_literal_template_escapes_percent():
    assert literal_template("", "100% Love (1)") == "100%% Love (1).%(ext)s"
    assert literal_template("Sub", "a [b]") == "Sub/a [b].%(ext)s"
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_command.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.command'`.

- [ ] **Step 3: Реализовать `ytgui/core/command.py`**

```python
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
```

- [ ] **Step 4: Запустить, убедиться что проходит**

Run: `.venv/bin/python -m pytest tests/test_command.py -v`
Expected: все PASS.

- [ ] **Step 5: Commit**

```bash
git add ytgui/core/command.py tests/test_command.py
git commit -m "feat: build yt-dlp commands" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: События и разбор прогресса

**Files:**
- Create: `ytgui/core/events.py`, `ytgui/core/progress.py`
- Test: `tests/test_progress.py`

**Interfaces:**
- Consumes: `PROGRESS_PREFIX` из `ytgui.core.command`.
- Produces:
  - `ytgui/core/events.py`: `@dataclass(frozen=True) class ProgressEvent(kind, text="", percent=None, downloaded=None, total=None, speed=None, eta=None, item_index=None, item_count=None)`, где `kind` один из `"download" | "item" | "stage" | "skipped" | "line"`; `@dataclass(frozen=True) class JobResult(status, message, exit_code=None, skipped=0)`, где `status` один из `"ok" | "error" | "cancelled"`.
  - `ytgui/core/progress.py`: `parse_line(line: str) -> ProgressEvent`, `format_bytes(n: float) -> str`, `describe_download(ev: ProgressEvent) -> str`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_progress.py`:
```python
from ytgui.core.events import ProgressEvent
from ytgui.core.progress import describe_download, format_bytes, parse_line


def test_download_line():
    ev = parse_line("YTG|downloading|1000|4000|NA|500.0|6")
    assert ev.kind == "download"
    assert ev.percent == 25.0
    assert (ev.downloaded, ev.total, ev.speed, ev.eta) == (1000, 4000, 500.0, 6)


def test_estimate_used_when_total_is_na():
    ev = parse_line("YTG|downloading|1000|NA|5000|NA|NA")
    assert ev.percent == 20.0
    assert ev.total == 5000
    assert ev.speed is None and ev.eta is None


def test_all_values_unknown():
    ev = parse_line("YTG|downloading|NA|NA|NA|NA|NA")
    assert ev.kind == "download"
    assert ev.percent is None and ev.downloaded is None and ev.total is None


def test_percent_is_capped_at_100():
    assert parse_line("YTG|finished|4100|4000|NA|NA|NA").percent == 100.0


def test_finished_line():
    ev = parse_line("YTG|finished|3433755|3433755|NA|254693.94410358524|NA")
    assert ev.percent == 100.0 and ev.text == "finished"


def test_malformed_progress_line_is_plain_line():
    ev = parse_line("YTG|oops")
    assert ev.kind == "line" and ev.text == "YTG|oops"


def test_playlist_item_line():
    ev = parse_line("[download] Downloading item 3 of 10")
    assert (ev.kind, ev.item_index, ev.item_count) == ("item", 3, 10)
    ev = parse_line("[download] Downloading video 2 of 5")
    assert (ev.item_index, ev.item_count) == (2, 5)


def test_stage_lines():
    assert parse_line("[ExtractAudio] Destination: /x/y.mp3") == ProgressEvent("stage", text="Конвертация аудио…")
    assert parse_line("[Merger] Merging formats into \"/x/y.mp4\"").text == "Объединение видео и аудио…"


def test_skipped_line():
    ev = parse_line("[download] /a/b.mp3 has already been downloaded")
    assert ev.kind == "skipped" and ev.text == "/a/b.mp3"


def test_other_line_is_log_without_newline():
    ev = parse_line("[youtube] abc: Downloading webpage\n")
    assert ev.kind == "line" and ev.text == "[youtube] abc: Downloading webpage"


def test_format_bytes():
    assert format_bytes(0) == "0 Б"
    assert format_bytes(1023) == "1023 Б"
    assert format_bytes(1536) == "1,5 КБ"
    assert format_bytes(int(12.4 * 1024 * 1024)) == "12,4 МБ"
    assert format_bytes(3 * 1024**3) == "3,0 ГБ"


def test_describe_download():
    ev = ProgressEvent("download", downloaded=13002342, total=20971520, speed=1887437.0)
    assert describe_download(ev) == "12,4 МБ из 20,0 МБ (1,8 МБ/с)"
    assert describe_download(ProgressEvent("download", downloaded=2048)) == "2,0 КБ"
    assert describe_download(ProgressEvent("download")) == ""
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_progress.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.events'`.

- [ ] **Step 3: Реализовать `ytgui/core/events.py`**

```python
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
```

- [ ] **Step 4: Реализовать `ytgui/core/progress.py`**

```python
"""Разбор строк stdout yt-dlp и форматирование размеров."""
from __future__ import annotations

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
        return float(raw)
    except ValueError:
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
```

- [ ] **Step 5: Запустить, убедиться что проходит**

Run: `.venv/bin/python -m pytest tests/test_progress.py -v`
Expected: все PASS.

- [ ] **Step 6: Commit**

```bash
git add ytgui/core/events.py ytgui/core/progress.py tests/test_progress.py
git commit -m "feat: progress events and line parser" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Понятные тексты ошибок

**Files:**
- Create: `ytgui/core/errors.py`
- Test: `tests/test_errors.py`

**Interfaces:**
- Produces (`ytgui/core/errors.py`): `FFMPEG_MISSING: str`, `YTDLP_MISSING: str`, `explain(lines: Iterable[str], exit_code: int | None = None) -> str`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_errors.py`:
```python
import pytest

from ytgui.core.errors import FFMPEG_MISSING, YTDLP_MISSING, explain


@pytest.mark.parametrize(
    "line,expected",
    [
        ("ERROR: [youtube] abc: Sign in to confirm you’re not a bot. Use --cookies-from-browser or --cookies for the authentication.", "не бот"),
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access to this video", "приватное"),
        ("ERROR: [youtube] abc: Sign in to confirm your age. This video may be inappropriate for some users.", "возраст"),
        ("ERROR: [youtube] abc: This video is unavailable", "недоступно"),
        ("ERROR: [youtube] abc: Video unavailable. This video contains content from X, who has blocked it in your country", "недоступно"),
        ("ERROR: [youtube] abc: Requested format is not available. Use --list-formats for a list of available formats", "формат"),
        ("ERROR: Unsupported URL: https://example.com/x", "не поддерживается"),
        ("ERROR: Postprocessing: ffprobe and ffmpeg not found. Please install or provide the path using --ffmpeg-location", "ffmpeg"),
        ("ERROR: unable to download video data: <urlopen error [Errno 8] nodename nor servname provided, or not known>", "интернет"),
        ("ERROR: could not find chrome cookies database in \"/Users/x/Library\"", "cookies"),
    ],
)
def test_known_errors(line, expected):
    assert expected in explain([line], 1).lower()


def test_unknown_error_strips_prefix():
    text = explain(["ERROR: [youtube] abc123XYZ_-: Something odd happened"], 1)
    assert text == "Something odd happened"


def test_last_error_wins():
    lines = ["ERROR: [youtube] a: This video is unavailable", "ERROR: [youtube] b: Private video"]
    assert "приватное" in explain(lines, 1)


def test_no_error_line_gives_generic_message_with_code():
    assert explain(["[download] something"], 2) == "Загрузка не удалась (код 2). Подробности в логе."
    assert explain([], None) == "Загрузка не удалась. Подробности в логе."


def test_noisy_warnings_and_tracebacks_are_ignored():
    noise = [
        "WARNING: [youtube] [jsc] Error solving 2 challenge requests using \"deno\" provider: Failed to load player",
        "         requests = [JsChallengeRequest(type=<JsChallengeType.N: 'n'>, input=NChallengeInput(player_url='x'))]",
        "Traceback (most recent call last):",
        '  File "yt_dlp/YoutubeDL.py", line 1, in extract',
    ]
    text = explain(noise, 1)
    assert "Traceback" not in text and "requests" not in text
    assert text.startswith("Загрузка не удалась")
    with_error = noise + ["ERROR: [youtube] abc: Private video"]
    assert "приватное" in explain(with_error, 1)


def test_long_message_is_truncated():
    text = explain(["ERROR: " + "x" * 1000], 1)
    assert len(text) <= 300 and text.endswith("…")


def test_tool_missing_constants_mention_brew():
    assert "brew install ffmpeg" in FFMPEG_MISSING
    assert "brew install yt-dlp" in YTDLP_MISSING
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_errors.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.errors'`.

- [ ] **Step 3: Реализовать `ytgui/core/errors.py`**

Порядок правил важен: сообщения о боте и возрасте сами упоминают `--cookies`, поэтому правило про cookies стоит после них.

```python
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
        r"unable to download|getaddrinfo|nodename nor servname|temporary failure|timed out|network is unreachable|connection reset|ssl|http error 5",
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
```

- [ ] **Step 4: Запустить, убедиться что проходит**

Run: `.venv/bin/python -m pytest tests/test_errors.py -v`
Expected: все PASS. Если какой-то случай не сработал, поправить регулярное выражение, а не тест.

- [ ] **Step 5: Commit**

```bash
git add ytgui/core/errors.py tests/test_errors.py
git commit -m "feat: human-readable yt-dlp errors" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Поиск утилит и уникальное имя

**Files:**
- Create: `ytgui/core/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces (`ytgui/core/paths.py`): `SYSTEM_DIRS: tuple[str, ...]`, `bundled_dir() -> str`, `find_tool(name: str, extra_dirs: Sequence[str] | None = None) -> str | None`, `unique_stem(folder: str, stem: str, ext: str) -> str`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_paths.py`:
```python
import os
import shutil
import sys
from pathlib import Path

from ytgui.core import paths


def make_exec(directory: Path, name: str, mode: int = 0o755) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    file = directory / name
    file.write_text("#!/bin/sh\n")
    file.chmod(mode)
    return file


def test_find_tool_prefers_extra_dirs(tmp_path, monkeypatch):
    mine = make_exec(tmp_path / "bin", "yt-dlp")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/other")
    assert paths.find_tool("yt-dlp", [str(tmp_path / "bin")]) == str(mine)


def test_find_tool_skips_non_executable(tmp_path, monkeypatch):
    make_exec(tmp_path / "bin", "ffmpeg", mode=0o644)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert paths.find_tool("ffmpeg", [str(tmp_path / "bin")]) == "/usr/bin/ffmpeg"


def test_find_tool_falls_back_to_system_dirs(tmp_path, monkeypatch):
    sysdir = tmp_path / "homebrew"
    tool = make_exec(sysdir, "ffmpeg")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(paths, "SYSTEM_DIRS", (str(sysdir),))
    assert paths.find_tool("ffmpeg", []) == str(tool)


def test_find_tool_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(paths, "SYSTEM_DIRS", (str(tmp_path / "none"),))
    assert paths.find_tool("nothing", []) is None


def test_bundled_dir_in_development_points_to_packaging_bin():
    assert paths.bundled_dir().endswith(os.path.join("packaging", "bin"))


def test_bundled_dir_when_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "App.app" / "Contents" / "MacOS" / "App"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    expected = (tmp_path / "App.app" / "Contents" / "Resources" / "bin").resolve()
    assert Path(paths.bundled_dir()) == expected


def test_unique_stem_free_name_unchanged(tmp_path):
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song"


def test_unique_stem_adds_numeric_suffix(tmp_path):
    (tmp_path / "Song.mp3").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song (1)"
    (tmp_path / "Song (1).mp3").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song (2)"


def test_unique_stem_only_same_extension_counts(tmp_path):
    (tmp_path / "Song.mp4").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song"


def test_unique_stem_with_special_and_cyrillic_names(tmp_path):
    name = "100% Любовь [Official]"
    (tmp_path / f"{name}.mp3").write_text("")
    assert paths.unique_stem(str(tmp_path), name, "mp3") == f"{name} (1)"


def test_unique_stem_missing_folder_is_free(tmp_path):
    assert paths.unique_stem(str(tmp_path / "нет"), "Song", "mp3") == "Song"
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.paths'`.

- [ ] **Step 3: Реализовать `ytgui/core/paths.py`**

```python
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
```

- [ ] **Step 4: Запустить, убедиться что проходит**

Run: `.venv/bin/python -m pytest tests/test_paths.py -v`
Expected: все PASS.

- [ ] **Step 5: Commit**

```bash
git add ytgui/core/paths.py tests/test_paths.py
git commit -m "feat: tool lookup and unique file names" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Настройки

**Files:**
- Create: `ytgui/core/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: константы из `ytgui.core.options`.
- Produces (`ytgui/core/settings.py`): `@dataclass class Settings(folder="", mode="audio", audio_format="mp3", audio_quality=0, video_format="mp4", max_height=None, template=DEFAULT_TEMPLATE, cookies_browser=None, open_folder=True)`, `settings_path() -> Path`, `load(path: str | Path | None = None) -> Settings`, `save(settings: Settings, path: str | Path | None = None) -> None` (бросает `OSError`, если записать нельзя).

- [ ] **Step 1: Написать падающие тесты**

`tests/test_settings.py`:
```python
import json

from ytgui.core.settings import Settings, load, save, settings_path


def test_default_path_is_in_application_support():
    p = settings_path()
    assert p.name == "settings.json"
    assert "Application Support" in str(p)


def test_roundtrip_with_cyrillic_folder(tmp_path):
    target = tmp_path / "s.json"
    original = Settings(
        folder="/Users/я/Музыка", mode="video", audio_format="opus", audio_quality=3,
        video_format="webm", max_height=720, template="%(uploader)s - %(title)s.%(ext)s",
        cookies_browser="firefox", open_folder=False,
    )
    save(original, target)
    assert load(target) == original
    assert "Музыка" in target.read_text(encoding="utf-8")


def test_missing_file_gives_defaults(tmp_path):
    assert load(tmp_path / "нет.json") == Settings()


def test_corrupt_json_gives_defaults(tmp_path):
    target = tmp_path / "s.json"
    target.write_text("{не json", encoding="utf-8")
    assert load(target) == Settings()


def test_empty_file_gives_defaults(tmp_path):
    target = tmp_path / "s.json"
    target.write_text("", encoding="utf-8")
    assert load(target) == Settings()


def test_non_object_json_gives_defaults(tmp_path):
    target = tmp_path / "s.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    assert load(target) == Settings()


def test_wrong_types_and_ranges_fall_back_per_field(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(
        json.dumps({
            "folder": "/ok", "audio_quality": "лучшее", "mode": "radio",
            "audio_format": "flac", "max_height": 360, "open_folder": "yes",
            "cookies_browser": "safari", "template": "  ",
        }),
        encoding="utf-8",
    )
    s = load(target)
    assert s.folder == "/ok"
    assert s == Settings(folder="/ok")


def test_bool_is_not_a_valid_quality(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"audio_quality": True}), encoding="utf-8")
    assert load(target).audio_quality == 0


def test_quality_out_of_range_falls_back(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"audio_quality": 99}), encoding="utf-8")
    assert load(target).audio_quality == 0


def test_unknown_keys_are_ignored(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"folder": "/a", "future_option": 1}), encoding="utf-8")
    assert load(target) == Settings(folder="/a")


def test_save_creates_parent_directories(tmp_path):
    target = tmp_path / "a" / "b" / "s.json"
    save(Settings(folder="/x"), target)
    assert load(target).folder == "/x"
    assert not (tmp_path / "a" / "b" / "s.tmp").exists()


def test_load_when_parent_is_a_file_gives_defaults(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert load(blocker / "s.json") == Settings()
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_settings.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.settings'`.

- [ ] **Step 3: Реализовать `ytgui/core/settings.py`**

```python
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
```

- [ ] **Step 4: Запустить, убедиться что проходит**

Run: `.venv/bin/python -m pytest tests/test_settings.py -v`
Expected: все PASS.

- [ ] **Step 5: Commit**

```bash
git add ytgui/core/settings.py tests/test_settings.py
git commit -m "feat: tolerant JSON settings" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Запуск yt-dlp и отмена (runner)

**Files:**
- Create: `ytgui/core/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `DownloadOptions` (Task 1); `build_command`, `build_probe_command`, `literal_template`, `PROBE_PREFIX` (Task 2); `ProgressEvent`, `JobResult` (Task 3); `parse_line` (Task 3); `explain`, `FFMPEG_MISSING`, `YTDLP_MISSING` (Task 4); `find_tool`, `unique_stem`, `bundled_dir`, `SYSTEM_DIRS` (Task 5).
- Produces (`ytgui/core/runner.py`):
  - `class DownloadJob`:
    `__init__(self, options: DownloadOptions, on_event: Callable[[ProgressEvent], None], ytdlp: str | None = None, ffmpeg: str | None = None, find: Callable[[str], str | None] = find_tool, kill_grace: float = 3.0)`;
    `run(self) -> JobResult` (блокирующий, вызывается из рабочего потока);
    `cancel(self) -> None` (потокобезопасный, можно вызывать когда угодно и многократно).
  - `child_env() -> dict[str, str]`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_runner.py`:
```python
import os
import stat
import sys
import threading
import time

import pytest

from ytgui.core.events import ProgressEvent
from ytgui.core.options import DownloadOptions
from ytgui.core.runner import DownloadJob, child_env

FAKE_YTDLP = """#!PYTHON
import os, sys, time
mode = os.environ.get("FAKE_MODE", "ok")
argv = sys.argv[1:]
if "--print" in argv:
    if mode == "unavailable":
        print("ERROR: [youtube] abc: This video is unavailable", file=sys.stderr)
        sys.exit(1)
    print("WARNING: [youtube] noise before the name")
    print("YTGFILE|" + os.environ.get("FAKE_NAME", "Song") + ".webm")
    sys.exit(0)
if os.environ.get("FAKE_ARGV"):
    with open(os.environ["FAKE_ARGV"], "w", encoding="utf-8") as f:
        f.write("\\n".join(argv))
if mode == "private":
    print("ERROR: [youtube] abc: Private video. Sign in if you've been granted access", file=sys.stderr)
    sys.exit(1)
if "--yes-playlist" in argv:
    print("[download] Downloading item 1 of 2", flush=True)
print("YTG|downloading|1000|4000|NA|500.0|6", flush=True)
if mode == "slow":
    print("YTG|downloading|2000|4000|NA|500.0|3", flush=True)
    time.sleep(30)
print("YTG|finished|4000|4000|NA|500.0|NA", flush=True)
print("[ExtractAudio] Destination: x.mp3", flush=True)
if mode == "skipped":
    print("[download] /tmp/x.mp3 has already been downloaded", flush=True)
sys.exit(0)
"""


@pytest.fixture
def fake(tmp_path):
    script = tmp_path / "fake-yt-dlp"
    script.write_text(FAKE_YTDLP.replace("PYTHON", sys.executable), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def make_job(tmp_path, fake, folder=None, find=None, **kw):
    folder = folder or tmp_path / "out"
    options = DownloadOptions(url="https://youtu.be/abc", folder=str(folder), **kw)
    events: list[ProgressEvent] = []
    extra = {"find": find} if find else {}
    job = DownloadJob(options, events.append, ytdlp=str(fake), ffmpeg="/bin/echo", kill_grace=0.5, **extra)
    return job, events


def test_success_creates_folder_and_emits_progress(tmp_path, fake):
    job, events = make_job(tmp_path, fake)
    result = job.run()
    assert result.status == "ok" and result.message == "Готово" and result.exit_code == 0
    assert (tmp_path / "out").is_dir()
    downloads = [e for e in events if e.kind == "download"]
    assert downloads[0].percent == 25.0 and downloads[-1].percent == 100.0
    assert any(e.kind == "stage" for e in events)


def test_folder_with_spaces_and_cyrillic(tmp_path, fake):
    job, _ = make_job(tmp_path, fake, folder=tmp_path / "Музыка и видео")
    assert job.run().status == "ok"
    assert (tmp_path / "Музыка и видео").is_dir()


def test_existing_file_gets_numeric_suffix_in_template(tmp_path, fake, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "Song.mp3").write_text("")
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_ARGV", str(argv_file))
    job, events = make_job(tmp_path, fake)
    assert job.run().status == "ok"
    argv = argv_file.read_text(encoding="utf-8").split("\n")
    assert argv[argv.index("-o") + 1] == "Song (1).%(ext)s"
    assert any("Song (1).mp3" in e.text for e in events if e.kind == "line")


def test_free_name_keeps_user_template(tmp_path, fake, monkeypatch):
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_ARGV", str(argv_file))
    job, _ = make_job(tmp_path, fake, template="%(uploader)s - %(title)s.%(ext)s")
    assert job.run().status == "ok"
    argv = argv_file.read_text(encoding="utf-8").split("\n")
    assert argv[argv.index("-o") + 1] == "%(uploader)s - %(title)s.%(ext)s"


def test_percent_in_title_is_escaped_in_suffix_template(tmp_path, fake, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "100% Любовь [Live].mp3").write_text("")
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_ARGV", str(argv_file))
    monkeypatch.setenv("FAKE_NAME", "100% Любовь [Live]")
    job, _ = make_job(tmp_path, fake)
    assert job.run().status == "ok"
    argv = argv_file.read_text(encoding="utf-8").split("\n")
    assert argv[argv.index("-o") + 1] == "100%% Любовь [Live] (1).%(ext)s"


def test_private_video_is_explained(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "private")
    result = make_job(tmp_path, fake)[0].run()
    assert result.status == "error" and "приватное" in result.message and result.exit_code == 1


def test_unavailable_video_fails_at_probe(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "unavailable")
    result = make_job(tmp_path, fake)[0].run()
    assert result.status == "error" and "недоступно" in result.message


def test_playlist_counts_skipped_files(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "skipped")
    job, events = make_job(tmp_path, fake, playlist=True)
    result = job.run()
    assert result.status == "ok" and result.skipped == 1 and "пропущено" in result.message
    assert any(e.kind == "item" and e.item_count == 2 for e in events)


def test_cancel_while_running_terminates_quickly(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "slow")
    reached = threading.Event()
    job, events = make_job(tmp_path, fake)
    job._on_event = lambda e: reached.set() if e.kind == "download" and e.percent == 50.0 else None
    box = {}
    thread = threading.Thread(target=lambda: box.update(result=job.run()))
    started = time.monotonic()
    thread.start()
    assert reached.wait(10)
    job.cancel()
    thread.join(10)
    assert not thread.is_alive()
    assert box["result"].status == "cancelled"
    assert time.monotonic() - started < 10


def test_cancel_before_start_never_spawns(tmp_path, fake):
    job, events = make_job(tmp_path, fake)
    job.cancel()
    assert job.run().status == "cancelled"
    assert events == []


def test_cancel_twice_and_after_finish_is_harmless(tmp_path, fake):
    job, _ = make_job(tmp_path, fake)
    assert job.run().status == "ok"
    job.cancel()
    job.cancel()


def test_missing_ffmpeg(tmp_path, fake):
    job = DownloadJob(
        DownloadOptions(url="https://youtu.be/abc", folder=str(tmp_path / "o")),
        lambda e: None, ytdlp=str(fake), find=lambda name: None,
    )
    result = job.run()
    assert result.status == "error" and "ffmpeg" in result.message
    assert not (tmp_path / "o").exists()


def test_missing_ytdlp(tmp_path):
    job = DownloadJob(
        DownloadOptions(url="https://youtu.be/abc", folder=str(tmp_path / "o")),
        lambda e: None, find=lambda name: None,
    )
    result = job.run()
    assert result.status == "error" and "yt-dlp" in result.message


def test_unrunnable_ytdlp_gives_message_not_crash(tmp_path):
    job = DownloadJob(
        DownloadOptions(url="https://youtu.be/abc", folder=str(tmp_path / "o")),
        lambda e: None, ytdlp="/nonexistent/yt-dlp", ffmpeg="/bin/echo",
    )
    result = job.run()
    assert result.status == "error" and "Не удалось запустить" in result.message


def test_invalid_options_message(tmp_path, fake):
    options = DownloadOptions(url="не ссылка", folder=str(tmp_path))
    result = DownloadJob(options, lambda e: None, ytdlp=str(fake), ffmpeg="/bin/echo").run()
    assert result.status == "error" and "ссылк" in result.message


@pytest.mark.skipif(os.geteuid() == 0, reason="root игнорирует права доступа")
def test_unwritable_folder(tmp_path, fake):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        result = make_job(tmp_path, fake, folder=locked)[0].run()
    finally:
        locked.chmod(0o700)
    assert result.status == "error" and "прав" in result.message


def test_folder_path_is_a_file(tmp_path, fake):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    result = make_job(tmp_path, fake, folder=blocker / "sub")[0].run()
    assert result.status == "error" and "папк" in result.message


def test_child_env_has_homebrew_and_unbuffered_output():
    env = child_env()
    assert "/opt/homebrew/bin" in env["PATH"].split(os.pathsep)
    assert env["PYTHONUNBUFFERED"] == "1" and env["PYTHONIOENCODING"] == "utf-8"
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.core.runner'`.

- [ ] **Step 3: Реализовать `ytgui/core/runner.py`**

```python
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
        self._tail: deque[str] = deque(maxlen=MAX_TAIL_LINES)

    # ---- публичный интерфейс -------------------------------------------------

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            proc = self._proc
        if proc is not None:
            self._signal_group(proc, signal.SIGTERM)
            timer = threading.Timer(self._kill_grace, self._signal_group, (proc, signal.SIGKILL))
            timer.daemon = True
            timer.start()

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
            if not options.playlist:
                options, failure = self._with_unique_name(options, ytdlp)
                if failure:
                    return failure
            return self._download(options, ytdlp, ffmpeg)
        except _Cancelled:
            return JobResult("cancelled", "Отменено")
        except OSError as exc:
            return JobResult("error", f"Не удалось запустить yt-dlp: {exc.strerror or exc}")

    # ---- внутреннее ------------------------------------------------------------

    @staticmethod
    def _signal_group(proc: subprocess.Popen, sig: int) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(proc.pid, sig)  # процесс запущен в своей группе, убиваем вместе с ffmpeg
        except (ProcessLookupError, PermissionError):
            pass

    def _stream(self, cmd: list[str], handle_line: Callable[[str], None]) -> int:
        with self._lock:
            if self._cancelled:
                raise _Cancelled
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
            self._proc = proc
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\r\n")
                if line:
                    handle_line(line)
            return proc.wait()
        finally:
            with self._lock:
                self._proc = None
            proc.stdout.close()

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
```

- [ ] **Step 4: Запустить, убедиться что проходит**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: все PASS (тест отмены занимает до пары секунд). Если `test_cancel_while_running_terminates_quickly` зависает, проблема в `_signal_group`/`start_new_session`, а не в тесте.

- [ ] **Step 5: Прогнать весь набор**

Run: `.venv/bin/python -m pytest -v`
Expected: все тесты задач 1–7 PASS.

- [ ] **Step 6: Commit**

```bash
git add ytgui/core/runner.py tests/test_runner.py
git commit -m "feat: yt-dlp runner with cancel and unique names" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Окно приложения

**Files:**
- Create: `ytgui/ui/style.py`, `ytgui/ui/worker.py`, `ytgui/ui/main_window.py`, `ytgui/__main__.py`
- Test: `tests/test_window.py`

**Interfaces:**
- Consumes: `DownloadOptions`, `Mode`, константы, `is_playlist_url` (Task 1); `ProgressEvent`, `JobResult` (Task 3); `describe_download` (Task 3); `Settings`, `load`, `save` (Task 6); `find_tool` (Task 5). `DownloadJob` из Task 7 импортируется лениво, поэтому модуль окна не требует готового runner.
- Produces:
  - `ytgui/ui/worker.py`: `class DownloadWorker(QThread)` с сигналами `event = Signal(object)` (ProgressEvent) и `done = Signal(object)` (JobResult); `__init__(self, options, job_factory=None)`; `cancel()`.
  - `ytgui/ui/main_window.py`: `class MainWindow(QWidget)`; `__init__(self, settings_path: str | Path | None = None, worker_factory=DownloadWorker)`. Публичные виджеты (используются тестами): `url_edit`, `audio_radio`, `video_radio`, `playlist_check`, `format_combo`, `height_combo`, `quality_slider`, `quality_value`, `quality_row`, `template_edit`, `cookies_combo`, `folder_edit`, `browse_button`, `open_folder_check`, `download_button`, `cancel_button`, `progress`, `status_label`, `detail_label`, `log`.
  - `ytgui/__main__.py`: `main() -> int`; флаг `--self-check` печатает найденные пути yt-dlp и ffmpeg и выходит.
- Контракт фабрики воркера: `worker_factory(options)` возвращает объект с сигналами `event`, `done` и методами `start()`, `cancel()`, `isRunning() -> bool`, `wait(msecs: int = 0) -> bool`, `deleteLater()`.

Макет: стиль и состав как на присланных скриншотах; приоритет у ТЗ. Слайдер качества: правый край = лучшее (качество 0), поэтому позиция слайдера `p` связана с качеством так: `quality = 9 - p`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_window.py`:
```python
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import QApplication, QFileDialog

from ytgui.core.events import JobResult, ProgressEvent
from ytgui.core.options import Mode
from ytgui.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


class FakeWorker(QObject):
    event = Signal(object)
    done = Signal(object)
    instances: list["FakeWorker"] = []

    def __init__(self, options):
        super().__init__()
        self.options = options
        self.started = False
        self.cancelled = False
        FakeWorker.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def isRunning(self):
        return self.started

    def wait(self, msecs=0):
        return True


@pytest.fixture
def window(app, tmp_path):
    FakeWorker.instances.clear()
    return MainWindow(settings_path=tmp_path / "settings.json", worker_factory=FakeWorker)


def fill(window, url="https://youtu.be/abc", folder="/tmp/out"):
    window.url_edit.setText(url)
    window.folder_edit.setText(folder)


def test_download_disabled_until_url_and_folder(window):
    assert not window.download_button.isEnabled() and not window.cancel_button.isEnabled()
    window.url_edit.setText("https://youtu.be/abc")
    assert not window.download_button.isEnabled()
    window.folder_edit.setText("/tmp/out")
    assert window.download_button.isEnabled()
    window.url_edit.setText("   ")
    assert not window.download_button.isEnabled()


def test_playlist_checkbox_follows_url(window):
    assert not window.playlist_check.isEnabled()
    window.url_edit.setText("https://www.youtube.com/playlist?list=PL1")
    assert window.playlist_check.isEnabled()
    window.playlist_check.setChecked(True)
    window.url_edit.setText("https://youtu.be/abc")
    assert not window.playlist_check.isEnabled() and not window.playlist_check.isChecked()


def test_mode_switch_changes_formats_and_rows(window):
    assert window.audio_radio.isChecked()
    assert [window.format_combo.itemText(i) for i in range(window.format_combo.count())] == ["MP3", "M4A", "OPUS", "WAV"]
    assert window.quality_row.isVisibleTo(window) and not window.height_combo.isVisibleTo(window)
    window.video_radio.setChecked(True)
    assert [window.format_combo.itemText(i) for i in range(window.format_combo.count())] == ["MP4", "MKV", "WebM"]
    assert window.height_combo.isVisibleTo(window) and not window.quality_row.isVisibleTo(window)


def test_wav_disables_quality_slider(window):
    assert window.quality_slider.isEnabled()
    window.format_combo.setCurrentIndex(3)
    assert not window.quality_slider.isEnabled()


def test_slider_right_end_is_best_quality(window):
    fill(window)
    window.quality_slider.setValue(9)
    assert window.quality_value.text().startswith("0")
    window.download_button.click()
    assert FakeWorker.instances[-1].options.audio_quality == 0


def test_start_builds_options_and_locks_ui(window):
    fill(window, folder="/tmp/Музыка")
    window.template_edit.setText("%(title)s [%(id)s].%(ext)s")
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    assert worker.started
    o = worker.options
    assert (o.url, o.folder, o.mode, o.audio_format) == ("https://youtu.be/abc", "/tmp/Музыка", Mode.AUDIO, "mp3")
    assert o.template == "%(title)s [%(id)s].%(ext)s" and o.playlist is False
    assert not window.download_button.isEnabled() and window.cancel_button.isEnabled()
    assert not window.url_edit.isEnabled() and not window.folder_edit.isEnabled()


def test_video_options_with_height_limit(window):
    fill(window)
    window.video_radio.setChecked(True)
    window.height_combo.setCurrentIndex(1)
    window.download_button.click()
    o = FakeWorker.instances[-1].options
    assert (o.mode, o.video_format, o.max_height) == (Mode.VIDEO, "mp4", 1080)


def test_progress_events_update_widgets(window):
    fill(window)
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    worker.event.emit(ProgressEvent("download", percent=62.0, downloaded=13002342, total=20971520, speed=1887437.0))
    assert window.progress.value() == 62
    assert "62%" in window.status_label.text()
    assert window.detail_label.text() == "12,4 МБ из 20,0 МБ (1,8 МБ/с)"
    worker.event.emit(ProgressEvent("item", text="[download] Downloading item 3 of 10", item_index=3, item_count=10))
    worker.event.emit(ProgressEvent("download", percent=10.0, downloaded=1, total=10))
    assert "3 из 10" in window.status_label.text()
    worker.event.emit(ProgressEvent("stage", text="Конвертация аудио…"))
    assert window.status_label.text() == "Конвертация аудио…"
    assert window.progress.maximum() == 0  # неопределённый индикатор
    worker.event.emit(ProgressEvent("line", text="[youtube] abc: Downloading webpage"))
    assert "Downloading webpage" in window.log.toPlainText()


def test_done_ok_reenables_ui_and_opens_folder(window, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url.toLocalFile())))
    fill(window, folder="/tmp/out")
    window.download_button.click()
    FakeWorker.instances[-1].done.emit(JobResult("ok", "Готово", 0))
    assert window.status_label.text() == "Готово" and window.progress.value() == 100
    assert window.download_button.isEnabled() and not window.cancel_button.isEnabled()
    assert window.url_edit.isEnabled()
    assert opened == ["/tmp/out"]


def test_done_ok_without_open_folder_option(window, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url)))
    fill(window)
    window.open_folder_check.setChecked(False)
    window.download_button.click()
    FakeWorker.instances[-1].done.emit(JobResult("ok", "Готово", 0))
    assert opened == []


def test_error_is_shown_as_plain_text(window):
    fill(window)
    window.download_button.click()
    FakeWorker.instances[-1].done.emit(JobResult("error", "Это приватное видео, доступ закрыт.", 1))
    assert window.status_label.text() == "Это приватное видео, доступ закрыт."
    assert window.status_label.property("error") is True
    assert window.download_button.isEnabled()


def test_cancel_button_cancels_worker_and_cancelled_result_resets(window):
    fill(window)
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    window.cancel_button.click()
    assert worker.cancelled and not window.cancel_button.isEnabled()
    worker.done.emit(JobResult("cancelled", "Отменено"))
    assert window.status_label.text() == "Отменено" and window.progress.value() == 0
    assert window.download_button.isEnabled()


def test_invalid_input_does_not_start_worker(window):
    fill(window, url="не ссылка")
    window.download_button.click()
    assert FakeWorker.instances == []
    assert "ссылк" in window.status_label.text()


def test_folder_persists_across_restart(app, tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    chosen = tmp_path / "Музыка"
    chosen.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(chosen)))
    first = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    first.browse_button.click()
    assert first.folder_edit.text() == str(chosen)
    second = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    assert second.folder_edit.text() == str(chosen)


def test_other_settings_are_restored(app, tmp_path):
    settings = tmp_path / "settings.json"
    first = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    first.video_radio.setChecked(True)
    first.format_combo.setCurrentIndex(2)  # WebM
    first.height_combo.setCurrentIndex(3)  # 480p
    first.cookies_combo.setCurrentIndex(1)  # Chrome
    first.open_folder_check.setChecked(False)
    first.url_edit.setText("https://youtu.be/abc")
    first.folder_edit.setText("/tmp/out")
    first.download_button.click()
    first.closeEvent(QCloseEvent())
    second = MainWindow(settings_path=settings, worker_factory=FakeWorker)
    assert second.video_radio.isChecked()
    assert second.format_combo.currentData() == "webm"
    assert second.height_combo.currentData() == 480
    assert second.cookies_combo.currentData() == "chrome"
    assert not second.open_folder_check.isChecked()


def test_unwritable_settings_do_not_break_start(app, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    window = MainWindow(settings_path=blocker / "s.json", worker_factory=FakeWorker)
    FakeWorker.instances.clear()
    fill(window)
    window.download_button.click()
    assert FakeWorker.instances[-1].started
    window.closeEvent(QCloseEvent())


def test_close_cancels_running_worker(window):
    fill(window)
    window.download_button.click()
    worker = FakeWorker.instances[-1]
    window.closeEvent(QCloseEvent())
    assert worker.cancelled


def test_window_width_is_fixed(window):
    assert window.minimumWidth() == window.maximumWidth() == 680
```

- [ ] **Step 2: Запустить, убедиться что падает**

Run: `.venv/bin/python -m pytest tests/test_window.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ytgui.ui.main_window'`.

- [ ] **Step 3: Реализовать `ytgui/ui/style.py`**

Цвета фона и текста полей не задаются, чтобы окно читалось и в тёмной теме macOS.

```python
STYLESHEET = """
QGroupBox { font-weight: 600; border: 1px solid palette(mid); border-radius: 8px;
            margin-top: 12px; padding: 12px 10px 8px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QLabel#caption { font-weight: 600; }
QLineEdit, QComboBox, QPlainTextEdit { border: 1px solid palette(mid); border-radius: 6px; padding: 5px 8px; }
QPushButton { border: 1px solid palette(mid); border-radius: 6px; padding: 6px 14px; }
QPushButton#primary { background: #1a73e8; color: white; border: none; font-weight: 600; padding: 8px 18px; }
QPushButton#primary:disabled { background: #8ab4f8; color: white; }
QProgressBar { border: none; background: palette(midlight); border-radius: 4px; max-height: 8px; }
QProgressBar::chunk { background: #1a73e8; border-radius: 4px; }
QLabel#status[error="true"] { color: #d93025; }
"""
```

- [ ] **Step 4: Реализовать `ytgui/ui/worker.py`**

```python
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
```

- [ ] **Step 5: Реализовать `ytgui/ui/main_window.py`**

```python
"""Единственное окно приложения."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSlider,
    QVBoxLayout, QWidget,
)

from ytgui.core import settings as settings_store
from ytgui.core.options import (
    AUDIO_FORMATS, COOKIE_BROWSERS, DEFAULT_TEMPLATE, HEIGHT_LIMITS, VIDEO_FORMATS,
    DownloadOptions, Mode, is_playlist_url,
)
from ytgui.core.progress import describe_download
from ytgui.ui.style import STYLESHEET
from ytgui.ui.worker import DownloadWorker

WINDOW_WIDTH = 680
FORMAT_LABELS = {"mp3": "MP3", "m4a": "M4A", "opus": "OPUS", "wav": "WAV", "mp4": "MP4", "mkv": "MKV", "webm": "WebM"}
HEIGHT_LABELS = {None: "Лучшее", 1080: "1080p", 720: "720p", 480: "480p"}
BROWSER_LABELS = {None: "Нет", "chrome": "Chrome", "firefox": "Firefox", "edge": "Edge"}


def quality_text(quality: int) -> str:
    if quality == 0:
        return "0 · лучшее"
    if quality == 9:
        return "9 · минимальное"
    return str(quality)


class MainWindow(QWidget):
    def __init__(self, settings_path: str | Path | None = None, worker_factory=DownloadWorker) -> None:
        super().__init__()
        self._settings_path = settings_path
        self._worker_factory = worker_factory
        self._worker = None
        self._item_prefix = ""
        self._formats = {"audio": "mp3", "video": "mp4"}
        self.setWindowTitle("YouTube Загрузчик")
        self.setFixedWidth(WINDOW_WIDTH)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._connect()
        self._apply_settings(settings_store.load(settings_path))
        self._refresh()

    # ---- построение окна -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        caption = QLabel("Ссылка")
        caption.setObjectName("caption")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Вставьте ссылку на ролик, шортс или плейлист")
        self.url_edit.setClearButtonEnabled(True)
        root.addWidget(caption)
        root.addWidget(self.url_edit)

        what = QGroupBox("Что скачать")
        what_row = QHBoxLayout(what)
        self.audio_radio = QRadioButton("Только аудио")
        self.video_radio = QRadioButton("Видео")
        self.playlist_check = QCheckBox("Скачать весь плейлист")
        what_row.addWidget(self.audio_radio)
        what_row.addWidget(self.video_radio)
        what_row.addStretch(1)
        what_row.addWidget(self.playlist_check)
        root.addWidget(what)

        fmt_box = QGroupBox("Формат")
        self._fmt_form = QFormLayout(fmt_box)
        self.format_combo = QComboBox()
        self.height_combo = QComboBox()
        for height in HEIGHT_LIMITS:
            self.height_combo.addItem(HEIGHT_LABELS[height], height)
        self._fmt_form.addRow("Формат", self.format_combo)
        self._fmt_form.addRow("Качество видео", self.height_combo)
        root.addWidget(fmt_box)

        par_box = QGroupBox("Параметры")
        self._par_form = QFormLayout(par_box)
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(0, 9)
        self.quality_slider.setPageStep(1)
        self.quality_value = QLabel()
        self.quality_value.setFixedWidth(110)
        self.quality_row = QWidget()
        quality_layout = QHBoxLayout(self.quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)
        quality_layout.addWidget(self.quality_slider, 1)
        quality_layout.addWidget(self.quality_value)
        self.template_edit = QLineEdit()
        self.cookies_combo = QComboBox()
        for browser in COOKIE_BROWSERS:
            self.cookies_combo.addItem(BROWSER_LABELS[browser], browser)
        self._par_form.addRow("Качество аудио", self.quality_row)
        self._par_form.addRow("Шаблон имени", self.template_edit)
        self._par_form.addRow("Cookies из браузера", self.cookies_combo)
        root.addWidget(par_box)

        save_box = QGroupBox("Куда сохранить")
        save_layout = QVBoxLayout(save_box)
        path_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Выберите папку")
        self.browse_button = QPushButton("Обзор…")
        path_row.addWidget(self.folder_edit, 1)
        path_row.addWidget(self.browse_button)
        self.open_folder_check = QCheckBox("Открыть папку после загрузки")
        save_layout.addLayout(path_row)
        save_layout.addWidget(self.open_folder_check)
        root.addWidget(save_box)

        buttons = QHBoxLayout()
        self.download_button = QPushButton("Скачать")
        self.download_button.setObjectName("primary")
        self.cancel_button = QPushButton("Отмена")
        buttons.addWidget(self.download_button, 1)
        buttons.addWidget(self.cancel_button)
        root.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Готов к загрузке")
        self.status_label.setObjectName("status")
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.detail_label)
        root.addLayout(status_row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(200)
        self.log.setFixedHeight(96)
        self.log.setPlaceholderText("Здесь появится журнал загрузки")
        root.addWidget(self.log)

        self._locked_while_running = (
            self.url_edit, self.audio_radio, self.video_radio, self.format_combo, self.height_combo,
            self.template_edit, self.cookies_combo, self.folder_edit, self.browse_button,
            self.open_folder_check,
        )

    def _connect(self) -> None:
        self.url_edit.textChanged.connect(self._refresh)
        self.folder_edit.textChanged.connect(self._refresh)
        self.folder_edit.editingFinished.connect(self._save_settings)
        self.audio_radio.toggled.connect(self._on_mode_changed)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        self.browse_button.clicked.connect(self._browse)
        self.download_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)

    # ---- состояние формы -------------------------------------------------------

    def _mode_key(self) -> str:
        return "audio" if self.audio_radio.isChecked() else "video"

    def _quality(self) -> int:
        return 9 - self.quality_slider.value()

    def _fill_formats(self) -> None:
        key = self._mode_key()
        formats = AUDIO_FORMATS if key == "audio" else VIDEO_FORMATS
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for fmt in formats:
            self.format_combo.addItem(FORMAT_LABELS[fmt], fmt)
        self.format_combo.setCurrentIndex(formats.index(self._formats[key]))
        self.format_combo.blockSignals(False)

    def _on_mode_changed(self) -> None:
        self._fill_formats()
        self._refresh()

    def _on_format_changed(self) -> None:
        self._formats[self._mode_key()] = self.format_combo.currentData()
        self._refresh()

    def _on_quality_changed(self) -> None:
        self.quality_value.setText(quality_text(self._quality()))

    def _refresh(self) -> None:
        running = self._worker is not None
        audio = self._mode_key() == "audio"
        is_playlist = is_playlist_url(self.url_edit.text())
        if not is_playlist:
            self.playlist_check.setChecked(False)
        self.playlist_check.setEnabled(is_playlist and not running)
        self._par_form.setRowVisible(self.quality_row, audio)
        self._fmt_form.setRowVisible(self.height_combo, not audio)
        for widget in self._locked_while_running:
            widget.setEnabled(not running)
        self.quality_slider.setEnabled(not running and self.format_combo.currentData() != "wav")
        can_start = bool(self.url_edit.text().strip()) and bool(self.folder_edit.text().strip())
        self.download_button.setEnabled(can_start and not running)
        self.cancel_button.setEnabled(running)
        self._fit_height()

    def _fit_height(self) -> None:
        self.layout().activate()
        height = self.sizeHint().height()
        if self.height() != height:
            self.resize(WINDOW_WIDTH, height)

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    # ---- настройки -------------------------------------------------------------

    def _apply_settings(self, s: settings_store.Settings) -> None:
        self._formats = {"audio": s.audio_format, "video": s.video_format}
        self.audio_radio.setChecked(s.mode == "audio")
        self.video_radio.setChecked(s.mode == "video")
        self._fill_formats()
        self.quality_slider.setValue(9 - s.audio_quality)
        self._on_quality_changed()
        self.height_combo.setCurrentIndex(HEIGHT_LIMITS.index(s.max_height))
        self.template_edit.setText(s.template)
        self.cookies_combo.setCurrentIndex(COOKIE_BROWSERS.index(s.cookies_browser))
        self.folder_edit.setText(s.folder)
        self.open_folder_check.setChecked(s.open_folder)

    def _save_settings(self) -> None:
        current = settings_store.Settings(
            folder=self.folder_edit.text().strip(),
            mode=self._mode_key(),
            audio_format=self._formats["audio"],
            audio_quality=self._quality(),
            video_format=self._formats["video"],
            max_height=self.height_combo.currentData(),
            template=self.template_edit.text().strip() or DEFAULT_TEMPLATE,
            cookies_browser=self.cookies_combo.currentData(),
            open_folder=self.open_folder_check.isChecked(),
        )
        try:
            settings_store.save(current, self._settings_path)
        except OSError as exc:
            self._append_log(f"Не удалось сохранить настройки: {exc.strerror or exc}")

    # ---- действия --------------------------------------------------------------

    def _build_options(self) -> DownloadOptions:
        return DownloadOptions(
            url=self.url_edit.text().strip(),
            folder=self.folder_edit.text().strip(),
            mode=Mode.AUDIO if self._mode_key() == "audio" else Mode.VIDEO,
            audio_format=self._formats["audio"],
            audio_quality=self._quality(),
            video_format=self._formats["video"],
            max_height=self.height_combo.currentData(),
            template=self.template_edit.text().strip() or DEFAULT_TEMPLATE,
            cookies_browser=self.cookies_combo.currentData(),
            playlist=self.playlist_check.isChecked(),
        )

    def _browse(self) -> None:
        start = self.folder_edit.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Выберите папку", start)
        if chosen:
            self.folder_edit.setText(chosen)
            self._save_settings()

    def _start(self) -> None:
        options = self._build_options()
        try:
            options.validate()
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self._save_settings()
        self.log.clear()
        self._item_prefix = ""
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.detail_label.clear()
        self._set_status("Подготовка…")
        self._worker = self._worker_factory(options)
        self._worker.event.connect(self._on_event)
        self._worker.done.connect(self._on_done)
        self._refresh()
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker is not None:
            self.cancel_button.setEnabled(False)
            self._set_status("Отмена…")
            self._worker.cancel()

    def _on_event(self, event) -> None:
        if event.kind == "download":
            if event.percent is not None:
                self.progress.setRange(0, 100)
                self.progress.setValue(int(event.percent))
                self._set_status(f"{self._item_prefix}Скачивание… {int(event.percent)}%")
            else:
                self.progress.setRange(0, 0)
                self._set_status(f"{self._item_prefix}Скачивание…")
            self.detail_label.setText(describe_download(event))
        elif event.kind == "item":
            self._item_prefix = f"Элемент {event.item_index} из {event.item_count}. "
            self._append_log(event.text)
        elif event.kind == "stage":
            self.progress.setRange(0, 0)
            self.detail_label.clear()
            self._set_status(event.text)
        elif event.kind == "skipped":
            self._append_log(f"Уже скачано: {event.text}")
        else:
            self._append_log(event.text)

    def _on_done(self, result) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.wait()
            worker.deleteLater()
        self.progress.setRange(0, 100)
        self.detail_label.clear()
        if result.status == "ok":
            self.progress.setValue(100)
            self._set_status(result.message)
            if self.open_folder_check.isChecked():
                QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_edit.text().strip()))
        elif result.status == "cancelled":
            self.progress.setValue(0)
            self._set_status(result.message)
        else:
            self.progress.setValue(0)
            self._set_status(result.message, error=True)
            self._append_log(result.message)
        self._refresh()

    def closeEvent(self, event) -> None:
        self._save_settings()
        worker = self._worker
        if worker is not None:
            worker.cancel()
            worker.wait(5000)
        event.accept()
```

- [ ] **Step 6: Реализовать `ytgui/__main__.py`**

```python
"""Точка входа: `python -m ytgui`."""
from __future__ import annotations

import sys


def main() -> int:
    if "--self-check" in sys.argv:
        from ytgui.core.paths import find_tool

        print("yt-dlp:", find_tool("yt-dlp"))
        print("ffmpeg:", find_tool("ffmpeg"))
        return 0

    from PySide6.QtWidgets import QApplication

    from ytgui.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("YT Загрузчик")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Запустить тесты окна**

Run: `.venv/bin/python -m pytest tests/test_window.py -v`
Expected: все PASS. Если падает проверка видимости (`isVisibleTo`) или `closeEvent`, чинить код окна, а не ослаблять тест.

- [ ] **Step 8: Проверить запуск и самопроверку**

Run: `.venv/bin/python -m ytgui --self-check`
Expected: две строки с путями к yt-dlp и ffmpeg (`/opt/homebrew/bin/...`).

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from PySide6.QtWidgets import QApplication; import sys; a=QApplication(sys.argv); from ytgui.ui.main_window import MainWindow; w=MainWindow(settings_path='/dev/null/x.json'); w.show(); print(w.width(), w.height())"`
Expected: печатается `680 <высота>` без исключений.

- [ ] **Step 9: Commit**

```bash
git add ytgui/ui ytgui/__main__.py tests/test_window.py
git commit -m "feat: main window, worker thread and entry point" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Сквозные проверки с реальной сетью

**Files:**
- Create: `tests/e2e/test_real_download.py`

**Interfaces:**
- Consumes: `DownloadJob` (Task 7), `DownloadOptions`, `Mode` (Task 1). Нужны `ffprobe` и сеть.

Тесты пропускаются без `YTGUI_E2E=1`. Файлы пишутся только в `tmp_path`.

- [ ] **Step 1: Написать тесты**

`tests/e2e/test_real_download.py`:
```python
import os
import subprocess
import threading
from pathlib import Path

import pytest

from ytgui.core.options import DownloadOptions, Mode
from ytgui.core.runner import DownloadJob

pytestmark = pytest.mark.skipif(
    os.environ.get("YTGUI_E2E") != "1", reason="сетевые тесты: запускать с YTGUI_E2E=1"
)
URL = os.environ.get("YTGUI_E2E_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def probe(path: Path, stream: str, entry: str) -> str:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", f"stream={entry}", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return out.strip().split("\n")[0]


def run(tmp_path, **kw):
    folder = tmp_path / "Музыка и видео"
    options = DownloadOptions(url=URL, folder=str(folder), **kw)
    result = DownloadJob(options, lambda event: None).run()
    files = sorted(folder.iterdir()) if folder.exists() else []
    return result, files


@pytest.mark.parametrize("fmt,codec", [("mp3", "mp3"), ("m4a", "aac"), ("opus", "opus"), ("wav", "pcm_s16le")])
def test_audio_formats(tmp_path, fmt, codec):
    result, files = run(tmp_path, audio_format=fmt)
    assert result.status == "ok", result.message
    assert [f.suffix for f in files] == [f".{fmt}"], files
    assert probe(files[0], "a:0", "codec_name") == codec


@pytest.mark.parametrize("fmt", ["mp4", "mkv", "webm"])
def test_video_height_limit_480(tmp_path, fmt):
    result, files = run(tmp_path, mode=Mode.VIDEO, video_format=fmt, max_height=480)
    assert result.status == "ok", result.message
    assert [f.suffix for f in files] == [f".{fmt}"], files
    assert int(probe(files[0], "v:0", "height")) <= 480


def test_repeat_download_does_not_overwrite(tmp_path):
    first, files = run(tmp_path)
    assert first.status == "ok", first.message
    second, files = run(tmp_path)
    assert second.status == "ok", second.message
    assert len(files) == 2
    assert any(" (1)" in f.stem for f in files)


def test_cancel_mid_download_leaves_no_final_file(tmp_path):
    folder = tmp_path / "out"
    options = DownloadOptions(url=URL, folder=str(folder), mode=Mode.VIDEO, video_format="mkv")
    started = threading.Event()
    job = DownloadJob(options, lambda e: started.set() if e.kind == "download" else None)
    box = {}
    thread = threading.Thread(target=lambda: box.update(result=job.run()))
    thread.start()
    assert started.wait(120)
    job.cancel()
    thread.join(30)
    assert not thread.is_alive()
    assert box["result"].status == "cancelled"
    assert not [f for f in folder.iterdir() if f.suffix == ".mkv"]


def test_unavailable_video_reports_readable_error(tmp_path):
    options = DownloadOptions(url="https://www.youtube.com/watch?v=jNQXAC9IJRE", folder=str(tmp_path / "o"))
    result = DownloadJob(options, lambda e: None).run()
    if result.status == "ok":
        pytest.skip("ролик снова доступен")
    assert result.status == "error"
    assert "Traceback" not in result.message and len(result.message) < 300
```

- [ ] **Step 2: Убедиться, что без флага тесты пропускаются**

Run: `.venv/bin/python -m pytest tests/e2e -v`
Expected: все SKIPPED.

- [ ] **Step 3: Запустить реальные проверки параллельно**

Разделить между агентами (у каждого свой `tmp_path`, конфликтов нет); ссылка по умолчанию длится 3,5 минуты, поэтому сеть может быть медленной:

- агент A: `YTGUI_E2E=1 .venv/bin/python -m pytest tests/e2e -k "audio_formats" -v`
- агент B: `YTGUI_E2E=1 .venv/bin/python -m pytest tests/e2e -k "video_height_limit" -v`
- агент C: `YTGUI_E2E=1 .venv/bin/python -m pytest tests/e2e -k "repeat or cancel or unavailable" -v`

Expected: все PASS. При сбое сети (SSL EOF, таймаут JS-challenge) повторить; при падении по сути (неверный кодек, нет суффикса) исправить `command.py`/`runner.py` и добавить юнит-тест в соответствующий файл.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e
git commit -m "test: opt-in end-to-end downloads" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Упаковка в .app и README

**Files:**
- Create: `packaging/entry.py`, `packaging/fetch_binaries.sh`, `packaging/build_app.sh`, `README.md`

**Interfaces:**
- Consumes: `ytgui.__main__.main` (Task 8, включая `--self-check`), `bundled_dir()` (Task 5: `Contents/Resources/bin` внутри `.app`).

- [ ] **Step 1: Создать скрипты**

`packaging/entry.py`:
```python
from ytgui.__main__ import main

raise SystemExit(main())
```

`packaging/fetch_binaries.sh`:
```bash
#!/usr/bin/env bash
# Скачивает автономные yt-dlp (universal2) и ffmpeg/ffprobe (arm64) в packaging/bin.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

curl -fL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos" -o bin/yt-dlp
for tool in ffmpeg ffprobe; do
  curl -fL "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/${tool}.zip" -o "$tmp/${tool}.zip"
  unzip -o "$tmp/${tool}.zip" -d "$tmp" > /dev/null
  mv "$tmp/${tool}" "bin/${tool}"
done
chmod +x bin/yt-dlp bin/ffmpeg bin/ffprobe
file bin/yt-dlp bin/ffmpeg bin/ffprobe
```

`packaging/build_app.sh`:
```bash
#!/usr/bin/env bash
# Собирает dist/YT Downloader.app. Сначала: packaging/fetch_binaries.sh
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in yt-dlp ffmpeg ffprobe; do
  [ -x "packaging/bin/$tool" ] || { echo "Нет packaging/bin/$tool. Запустите packaging/fetch_binaries.sh" >&2; exit 1; }
done
rm -rf build dist
.venv/bin/python -m PyInstaller --noconfirm --windowed --name "YT Downloader" \
  --osx-bundle-identifier local.ytgui.downloader --paths . packaging/entry.py
APP="dist/YT Downloader.app"
mkdir -p "$APP/Contents/Resources/bin"
cp packaging/bin/yt-dlp packaging/bin/ffmpeg packaging/bin/ffprobe "$APP/Contents/Resources/bin/"
codesign --force --sign - "$APP"
codesign --verify --verbose "$APP"
echo "Готово: $APP"
```

Run: `chmod +x packaging/fetch_binaries.sh packaging/build_app.sh`

- [ ] **Step 2: Проверить доступность ссылок**

Run:
```bash
curl -s -L -o /dev/null -w "%{http_code}\n" "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip"
curl -s -L -o /dev/null -w "%{http_code}\n" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
```
Expected: ответы `200`. Если ссылка на ffmpeg не работает, остановиться и сообщить пользователю, не подставлять другой источник самостоятельно.

- [ ] **Step 3: Скачать утилиты и проверить архитектуру**

Run: `packaging/fetch_binaries.sh && packaging/bin/yt-dlp --version && packaging/bin/ffmpeg -version | head -1 && packaging/bin/ffprobe -version | head -1`
Expected: `file` показывает Mach-O (yt-dlp: universal, ffmpeg/ffprobe: arm64), все три команды печатают версии.

- [ ] **Step 4: Собрать приложение**

Run: `packaging/build_app.sh`
Expected: последняя строка `Готово: dist/YT Downloader.app`, `codesign --verify` без ошибок.

- [ ] **Step 5: Проверить приложение изнутри**

Run: `"dist/YT Downloader.app/Contents/MacOS/YT Downloader" --self-check`
Expected: пути обоих инструментов указывают внутрь `dist/YT Downloader.app/Contents/Resources/bin/`.

Run: `"dist/YT Downloader.app/Contents/Resources/bin/yt-dlp" --version`
Expected: печатается версия (подписанный пакет не испортил автономный бинарник). Если печатается ошибка запуска или `killed`, не подписывать `yt-dlp`: убедиться, что `codesign` вызван без `--deep`, и сообщить пользователю.

Run:
```bash
open -n "dist/YT Downloader.app"
until pgrep -f "YT Downloader.app/Contents/MacOS" > /dev/null; do sleep 1; done
sleep 3 && pgrep -f "YT Downloader.app/Contents/MacOS" && echo "работает"
pkill -f "YT Downloader.app/Contents/MacOS"
```
Expected: `работает`, процесс не упал за 3 секунды.

Дополнительно (глазами, один раз): запустить `.app`, вставить ссылку, выбрать папку, скачать MP3. Окно должно обновлять прогресс, не зависать, а после перезапуска помнить папку.

- [ ] **Step 6: README**

`README.md`:
````markdown
# YT Загрузчик

Однооконная программа для macOS: ссылка → формат → папка → «Скачать». Внутри yt-dlp и ffmpeg.

## Запуск из исходников

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m ytgui
```

Нужны `yt-dlp` и `ffmpeg` (`brew install yt-dlp ffmpeg`) либо файлы в `packaging/bin`.

## Тесты

```bash
.venv/bin/python -m pytest                      # без сети
YTGUI_E2E=1 .venv/bin/python -m pytest tests/e2e  # реальные загрузки (нужна сеть и ffprobe)
```

## Сборка .app

```bash
packaging/fetch_binaries.sh   # yt-dlp и ffmpeg в packaging/bin
packaging/build_app.sh        # dist/YT Downloader.app
```

Настройки: `~/Library/Application Support/YT Загрузчик/settings.json`.
````

- [ ] **Step 7: Commit**

`packaging/bin/`, `build/` и `dist/` игнорируются через `.gitignore`.

```bash
git add packaging/entry.py packaging/fetch_binaries.sh packaging/build_app.sh README.md
git commit -m "build: PyInstaller .app packaging and README" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Самопроверка плана по спеку

- Окно и блоки (спек «Окно»): Task 8; порядок блоков, активность «Скачать», блокировка полей, создание папки (Task 7).
- Команды yt-dlp, WebM/MP4-селекторы, плейлист, cookies, прогресс: Task 2, Task 3.
- Повторное скачивание (суффикс для одного видео, `--no-overwrites` для плейлиста): Task 2 (команда), Task 5 (`unique_stem`), Task 7 (проба имени); реальная проверка в Task 9.
- Ошибки, проверка ffmpeg до запуска, отмена SIGTERM → SIGKILL, файлы `.part` не трогаются: Task 4, Task 7.
- Настройки (путь переживает перезапуск): Task 6, Task 8 (`test_folder_persists_across_restart`).
- Проверка: pytest без сети (Task 1–8), подставной yt-dlp (Task 7), офлайн-тест окна (Task 8), реальный запуск (Task 9).
- Упаковка (`.app`, бинарники рядом, порядок поиска): Task 5 (`bundled_dir`/`find_tool`), Task 10.
- Типы согласованы: `ProgressEvent`/`JobResult` определены в Task 3 и используются в Task 7 и 8 с теми же полями; `DownloadOptions.final_ext`/`clean_url` из Task 1 используются в Task 2 и 7; `literal_template` и `PROBE_PREFIX` из Task 2 используются в Task 7.
- Известное ограничение v1: при видео с отдельными дорожками полоса прогресса проходит 0–100 % дважды (видео, затем аудио). Спеком это не оговорено, оставлено как есть.
