import os
import stat
import sys
import threading
import time

import pytest

from ytgui.core.events import ProgressEvent
from ytgui.core.options import DownloadOptions, Mode
from ytgui.core.runner import DownloadJob, child_env

FAKE_YTDLP = """#!PYTHON
import os, signal, subprocess, sys, time
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
if mode in ("stubborn", "childonly"):
    if mode == "stubborn":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"])
    with open(os.environ["FAKE_PIDS"], "w", encoding="utf-8") as f:
        f.write(str(os.getpid()) + "\\n" + str(child.pid) + "\\n")
    time.sleep(0.5)  # дать потомку успеть выставить SIG_IGN
    print("YTG|downloading|2000|4000|NA|500.0|3", flush=True)
    time.sleep(30)
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


def _run_and_get_template(tmp_path, fake, monkeypatch, **kw):
    argv_file = tmp_path / "argv.txt"
    monkeypatch.setenv("FAKE_ARGV", str(argv_file))
    job, _ = make_job(tmp_path, fake, **kw)
    assert job.run().status == "ok"
    argv = argv_file.read_text(encoding="utf-8").split("\n")
    return argv[argv.index("-o") + 1]


def test_audio_mode_does_not_reuse_existing_webm_intermediate(tmp_path, fake, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "Song.webm").write_text("")
    template = _run_and_get_template(tmp_path, fake, monkeypatch)
    assert template == "Song (1).%(ext)s"


def test_video_mode_ignores_other_extensions(tmp_path, fake, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "Song.webm").write_text("")
    template = _run_and_get_template(
        tmp_path, fake, monkeypatch, mode=Mode.VIDEO, video_format="mp4"
    )
    assert template == "%(title)s.%(ext)s"


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


def test_probe_failure_output_reaches_the_log(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "unavailable")
    job, events = make_job(tmp_path, fake)
    job.run()
    assert any("This video is unavailable" in e.text for e in events if e.kind == "line")


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
    try:
        assert reached.wait(10)
        job.cancel()
        thread.join(10)
        assert not thread.is_alive()
        assert box["result"].status == "cancelled"
        assert time.monotonic() - started < 10
    finally:
        job.cancel()


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


def test_child_env_drops_pyinstaller_bootloader_variables(monkeypatch):
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", "x")
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", "y")
    env = child_env()
    assert "_PYI_ARCHIVE_FILE" not in env and "_PYI_APPLICATION_HOME_DIR" not in env
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"


def read_pids(path):
    return [int(x) for x in path.read_text(encoding="utf-8").split()]


def wait_gone(pids, timeout=2.0):
    deadline = time.monotonic() + timeout
    alive = list(pids)
    while alive and time.monotonic() < deadline:
        still = []
        for pid in alive:
            try:
                os.kill(pid, 0)
                still.append(pid)
            except ProcessLookupError:
                pass
        alive = still
        if alive:
            time.sleep(0.05)
    return alive


@pytest.mark.parametrize("mode", ["stubborn", "childonly"])
def test_cancel_kills_stubborn_process_and_its_child(tmp_path, fake, monkeypatch, mode):
    # stubborn: yt-dlp и ffmpeg игнорируют SIGTERM; childonly: yt-dlp умирает, а ffmpeg держит pipe
    pids_file = tmp_path / "pids.txt"
    monkeypatch.setenv("FAKE_MODE", mode)
    monkeypatch.setenv("FAKE_PIDS", str(pids_file))
    reached = threading.Event()
    job, _ = make_job(tmp_path, fake)
    job._on_event = lambda e: reached.set() if e.kind == "download" and e.percent == 50.0 else None
    box = {}
    thread = threading.Thread(target=lambda: box.update(result=job.run()))
    started = time.monotonic()
    thread.start()
    try:
        assert reached.wait(10)
        job.cancel()
        thread.join(5)
        assert not thread.is_alive()
        assert box["result"].status == "cancelled"
        assert time.monotonic() - started < 6
        pids = read_pids(pids_file)
        assert len(pids) == 2
        assert wait_gone(pids) == []
    finally:
        job.cancel()
        thread.join(5)


@pytest.mark.parametrize("error", [RuntimeError("boom"), OSError(5, "boom")])
def test_failing_callback_does_not_leave_process_behind(tmp_path, fake, monkeypatch, error):
    pids_file = tmp_path / "pids.txt"
    monkeypatch.setenv("FAKE_MODE", "stubborn")
    monkeypatch.setenv("FAKE_PIDS", str(pids_file))
    job, _ = make_job(tmp_path, fake)

    def boom(event):
        if event.kind == "download":
            raise error

    job._on_event = boom
    try:
        result = job.run()
        assert result.status == "error" and "Внутренняя ошибка" in result.message
        assert "Не удалось запустить" not in result.message
        pids = read_pids(pids_file)
        assert len(pids) == 2
        assert wait_gone(pids) == []
    finally:
        job.cancel()
