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
