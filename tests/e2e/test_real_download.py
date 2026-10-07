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
