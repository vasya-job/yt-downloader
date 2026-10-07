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
