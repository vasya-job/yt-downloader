# YT Загрузчик (downloader)

Однооконная программа для macOS над yt-dlp: вставить ссылку, выбрать аудио или видео, формат, папку и нажать «Скачать». Python 3.11 + PySide6; ядро (`ytgui/core`) не зависит от Qt и проверяется без окна. Публичная копия исходников: https://github.com/vasya-job/yt-downloader (MIT). Установленное приложение: `~/Applications/YT Downloader.app`.

## Сначала прочитай
1. `docs/BACKLOG.md` — что сделано (с коммитами) и что открыто. Обновляется каждым коммитом.
2. `docs/superpowers/specs/2026-10-07-yt-downloader-design.md` — дизайн и требования; `docs/superpowers/plans/…` — план реализации.
3. `README.md` (запуск, тесты, сборка, ограничения) и `THIRD_PARTY_NOTICES.md` (лицензии зависимостей).

## Структура
```
ytgui/core/    options, command, events, progress, errors, paths, settings, runner (без Qt)
ytgui/ui/      main_window, worker (QThread), style
ytgui/__main__.py   запуск; флаг --self-check печатает найденные yt-dlp и ffmpeg
tests/         юнит-тесты (без сети), tests/e2e — реальные загрузки (только YTGUI_E2E=1)
packaging/     fetch_binaries.sh, build_app.sh (PyInstaller), make_icon.py, icon.icns; packaging/bin — не в git
```

## Команды (из корня проекта)
- Среда: `/opt/homebrew/bin/python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` (на Python 3.14 PySide6 не ставится).
- Запуск: `.venv/bin/python -m ytgui`. Тесты: `.venv/bin/python -m pytest -q` (ожидается 148 passed, 10 skipped). Реальные загрузки: `YTGUI_E2E=1 .venv/bin/python -m pytest tests/e2e` (нужна сеть и ffprobe).
- Сборка `.app`: `packaging/fetch_binaries.sh` (yt-dlp и ffmpeg в `packaging/bin`), затем `packaging/build_app.sh` → `dist/YT Downloader.app`. После сборки приложение копируется в `~/Applications`.

## Правила проекта (обязательно)

**Git.**
- Git-каталог **вне Яндекс.Диска**: `~/projects/git-repos/downloader.git`, в папке проекта файл-указатель `.git` (`gitdir: …`). `git status/add/commit` работают как обычно. Нельзя: удалять файл `.git`, делать `git init` в папке, переносить папку или `downloader.git`, не поправив оба абсолютных пути.
- Каждый законченный шаг — **отдельный коммит**, и в том же коммите обновлён `docs/BACKLOG.md`.
- Сообщения коммитов краткие, заканчиваются трейлером `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Перед коммитом проверять индекс на секреты (у проекта секретов нет, но проверка обязательна: ключи, токены, пароли, `.env`, адреса вида `…/macros/s/<ID>`).
- **В локальной истории стоит личная почта автора. Из локального репозитория в GitHub не пушить.** У локального репозитория нет remote намеренно.

**Публикация на GitHub (только по просьбе владельца).** Публичный репозиторий `vasya-job/yt-downloader` ведётся отдельно, с авторством `231516971+vasya-job@users.noreply.github.com` (в аккаунте включены «Keep my email addresses private» и блокировка пушей с личной почтой). Порядок: свежий клон публичного репозитория в временную папку → перенести новые локальные коммиты (последний уже опубликованный локальный: `f67571d`) через `git cherry-pick -n <хэш>` и закоммитить с `GIT_AUTHOR_NAME/EMAIL` и `GIT_COMMITTER_NAME/EMAIL` = `vasya-job` / noreply → проверить `git log --format='%an %ae %cn %ce'` → `git push`. Перед этим просканировать индекс на секреты и личные данные. Готовое `.app` в релизы класть только вместе с лицензиями (см. `THIRD_PARTY_NOTICES.md`).

**Секреты.** У проекта секретов нет. Если появятся: только в `~/projects/git-repos/downloader_secrets/` (папка 700, файлы 600) или в Keychain и в копии на диске `base` (её делает только `disky-backup`); не на Яндекс.Диск, не в GitHub, не в облака и мессенджеры, значения не печатать в чат, логи и документы; в репозиторий не коммитить (`.gitignore`).

**Бэклог.** `docs/BACKLOG.md` обязателен: см. «Git».

**Бэкап.** Проект в ночном бэкапе (`disky-backup --add .` выполнено). Вручную `disky-backup .` — только по просьбе владельца или перед рискованной операцией.

**Агенты.** Независимые части задачи делать несколькими агентами параллельно, одним сообщением. Каждый агент, который пишет в репозиторий, работает в своём worktree и кладёт коммиты на свою ветку; слияние делает основной сеанс.

## Правила кода
- Ядро `ytgui/core` не импортирует Qt; всё Qt-зависимое только в `ytgui/ui`.
- Тексты интерфейса и сообщений по-русски, с корректной орфографией.
- Команда yt-dlp собирается списком аргументов (без shell); `%` в шаблонах имён экранируется как `%%`; ссылка должна быть `http(s)`.
- Любое изменение поведения начинается с падающего теста; тесты не ходят в сеть (сетевые только в `tests/e2e` с `YTGUI_E2E=1`) и не пишут вне `tmp_path`.
- Окно держит ширину 680 px, высоту по содержимому; цвета полей берутся из палитры системы (поддержка тёмной темы).
