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
