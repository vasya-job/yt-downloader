import pytest

from ytgui.core.errors import FFMPEG_MISSING, YTDLP_MISSING, explain


@pytest.mark.parametrize(
    "line,expected",
    [
        ("ERROR: [youtube] abc: Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication.", "не бот"),
        ("ERROR: [youtube] abc: Private video. Sign in if you've been granted access to this video", "приватное"),
        ("ERROR: [youtube] abc: Sign in to confirm your age. This video may be inappropriate for some users.", "возраст"),
        ("ERROR: [youtube] abc: This video is unavailable", "недоступно"),
        ("ERROR: [youtube] abc: Video unavailable. This video contains content from X, who has blocked it in your country", "недоступно"),
        ("ERROR: [youtube] abc: Requested format is not available. Use --list-formats for a list of available formats", "формат"),
        ("ERROR: Unsupported URL: https://example.com/x", "не поддерживается"),
        ("ERROR: Postprocessing: ffprobe and ffmpeg not found. Please install or provide the path using --ffmpeg-location", "не найден ffmpeg"),
        ("ERROR: ffprobe not found. Please install", "не найден ffmpeg"),
        ("ERROR: unable to download video data: <urlopen error [Errno 8] nodename nor servname provided, or not known>", "интернет"),
        ("ERROR: could not find chrome cookies database in \"/Users/x/Library\"", "cookies браузера"),
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
    assert "`" not in FFMPEG_MISSING and "`" not in YTDLP_MISSING


def test_http_403_error():
    text = explain(["ERROR: unable to download webpage: HTTP Error 403: Forbidden"], 1)
    assert "отказал" in text
    assert "интернет" not in text.lower()


def test_http_429_error():
    text = explain(["ERROR: [youtube] abc: Unable to download webpage: HTTP Error 429: Too Many Requests"], 1)
    assert "отказал" in text
    assert "интернет" not in text.lower()
