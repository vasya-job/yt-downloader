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

Иконка генерируется скриптом `packaging/make_icon.py` (пересоздать: `.venv/bin/python packaging/make_icon.py`).

Настройки: `~/Library/Application Support/YT Загрузчик/settings.json`.

## Ограничения и заметки

- ffmpeg и ffprobe в сборке только для arm64. На Mac с процессором Intel сначала будет использована встроенная копия, поэтому приложение нужно пересобрать с Intel-версиями.
- Приложение подписано ad-hoc. Если скопировать .app на другой Mac, система поместит его в карантин: выполните `xattr -dr com.apple.quarantine "YT Downloader.app"` или откройте через правый клик → «Открыть».
- Для YouTube на компьютере нужен deno (или другой JS-движок). Приложение добавляет `/opt/homebrew/bin` и `/usr/local/bin` в PATH для yt-dlp.
- Встроенный yt-dlp устаревает. Обновите его командой `packaging/fetch_binaries.sh`, затем пересоберите `packaging/build_app.sh`.
- `packaging/build_app.sh` требует созданный `.venv` с установленным `requirements-dev.txt`.
- Ссылка на плейлист при выключенной галочке «Скачать весь плейлист» скачает только первый элемент.
- Для плейлиста (галочка включена) уже существующий файл yt-dlp пропускает (`--no-overwrites`). Если звук элемента плейлиста совпадает с промежуточным файлом другого расширения, имя не меняется.

## Версия

Версия программы задаётся в одном месте: `ytgui/__version__` в `ytgui/__init__.py` (формат `мажор.минор.патч`). Её видно в нижнем правом углу окна, в `python -m ytgui --version` и в свойствах собранного `.app` (`build_app.sh` записывает её в `Info.plist`). Поднимайте версию перед сборкой нового выпуска.

## Лицензия

Код распространяется по лицензии MIT, см. [LICENSE](LICENSE). Сторонние компоненты и их лицензии: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
