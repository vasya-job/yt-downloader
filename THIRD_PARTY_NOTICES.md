# Сторонние компоненты

Исходный код этого репозитория распространяется по лицензии MIT (см. `LICENSE`).
Программа использует перечисленные ниже компоненты. Их файлов в репозитории нет:
Python-зависимости ставятся через `pip`, а `yt-dlp` и `ffmpeg` скачивает скрипт
`packaging/fetch_binaries.sh` на вашу машину.

| Компонент | Для чего | Лицензия | Где взять исходники |
|---|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | скачивание | Unlicense (общественное достояние) | https://github.com/yt-dlp/yt-dlp |
| [FFmpeg](https://ffmpeg.org/) | конвертация и склейка | сборка `ffmpeg.martin-riedl.de`: **GPLv3** (`--enable-gpl --enable-version3`, внутри x264 и x265) | https://ffmpeg.org/download.html#get-sources, страница сборки: https://ffmpeg.martin-riedl.de/ |
| [PySide6 / Qt](https://doc.qt.io/qtforpython-6/) | окно | LGPLv3 (или GPLv3 / коммерческая) | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| [PyInstaller](https://pyinstaller.org/) | сборка `.app` (только при сборке) | GPLv2+ с исключением для собираемых программ | https://github.com/pyinstaller/pyinstaller |
| [pytest](https://pytest.org/) | тесты (только разработка) | MIT | https://github.com/pytest-dev/pytest |
| [deno](https://deno.com/) | необязательно: JS-среда для yt-dlp на YouTube | MIT | https://github.com/denoland/deno |

## Если вы распространяете собранное `.app`

Внутри `.app` лежат `yt-dlp` и `ffmpeg`. Тогда вместе с приложением:

- приложите тексты лицензий GPLv3 (ffmpeg, x264, x265), LGPLv3 (Qt/PySide6) и Unlicense (yt-dlp);
- укажите, где взять исходники ffmpeg и сборки (ссылки в таблице выше);
- сохраните возможность заменить библиотеки Qt (так и устроена папочная сборка PyInstaller).

ffmpeg запускается отдельным процессом и не линкуется с кодом программы, поэтому
лицензия GPL на собственный код программы не распространяется. Этот файл не
является юридической консультацией.
