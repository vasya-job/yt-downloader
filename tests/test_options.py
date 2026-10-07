import pytest

from ytgui.core.options import DownloadOptions, Mode, is_playlist_url


def make(**kw):
    base = dict(url="https://youtu.be/abc", folder="/tmp/out")
    base.update(kw)
    return DownloadOptions(**base)


def test_valid_options_pass():
    make().validate()


def test_clean_url_strips_spaces():
    assert make(url="  https://youtu.be/abc \n").clean_url == "https://youtu.be/abc"


@pytest.mark.parametrize("url", ["", "   ", "youtube.com/watch?v=1", "ftp://x.org/a", "https://"])
def test_bad_url_rejected(url):
    with pytest.raises(ValueError, match="ссылк"):
        make(url=url).validate()


def test_empty_folder_rejected():
    with pytest.raises(ValueError, match="папк"):
        make(folder="  ").validate()


def test_empty_template_rejected():
    with pytest.raises(ValueError, match="Шаблон"):
        make(template=" ").validate()


@pytest.mark.parametrize(
    "kw",
    [
        {"audio_format": "flac"},
        {"video_format": "avi"},
        {"audio_quality": 10},
        {"audio_quality": -1},
        {"max_height": 360},
        {"cookies_browser": "safari"},
    ],
)
def test_unknown_values_rejected(kw):
    with pytest.raises(ValueError):
        make(**kw).validate()


def test_final_ext_follows_mode():
    assert make(mode=Mode.AUDIO, audio_format="opus").final_ext == "opus"
    assert make(mode=Mode.VIDEO, video_format="mkv").final_ext == "mkv"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=abc", False),
        ("https://www.youtube.com/watch?v=abc&list=PL123", True),
        ("https://www.youtube.com/playlist?list=PL123", True),
        ("https://youtu.be/abc?list=PL123", True),
        ("https://www.youtube.com/shorts/abc", False),
        ("  https://www.youtube.com/playlist?list=PL1  ", True),
        ("", False),
        ("не ссылка", False),
    ],
)
def test_is_playlist_url(url, expected):
    assert is_playlist_url(url) is expected
