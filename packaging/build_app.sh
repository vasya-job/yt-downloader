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
