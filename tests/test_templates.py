import pytest

from ytgui.core.command import playlist_template
from ytgui.core.options import DEFAULT_TEMPLATE
from ytgui.core.templates import CUSTOM_LABEL, PRESETS, ensure_extension, preset_index, preview_name


def test_presets_are_exact_and_default_first():
    assert PRESETS == (
        ("Название", "%(title)s.%(ext)s"),
        ("Автор — Название", "%(uploader)s - %(title)s.%(ext)s"),
        ("Название [код видео]", "%(title)s [%(id)s].%(ext)s"),
        ("Дата — Название", "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s"),
    )
    assert PRESETS[0][1] == DEFAULT_TEMPLATE
    assert CUSTOM_LABEL == "Свой шаблон…"


def test_preset_index():
    for index, (_label, template) in enumerate(PRESETS):
        assert preset_index(template) == index
    assert preset_index("%(title)s") is None
    assert preset_index("") is None
    assert preset_index("%(title)s.%(ext)s ") is None  # сравнение точное


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("%(title)s.%(ext)s", "%(title)s.%(ext)s"),
        ("%(title)s", "%(title)s.%(ext)s"),
        ("  %(uploader)s - %(title)s  ", "%(uploader)s - %(title)s.%(ext)s"),
        ("  %(title)s.%(ext)s\n", "%(title)s.%(ext)s"),
        ("", DEFAULT_TEMPLATE),
        ("   \t", DEFAULT_TEMPLATE),
        ("клип", "клип.%(ext)s"),
    ],
)
def test_ensure_extension(template, expected):
    assert ensure_extension(template) == expected


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        (PRESETS[0][1], "Название ролика.mp3"),
        (PRESETS[1][1], "Автор канала - Название ролика.mp3"),
        (PRESETS[2][1], "Название ролика [dQw4w9WgXcQ].mp3"),
        (PRESETS[3][1], "2026-10-08 - Название ролика.mp3"),
    ],
)
def test_preview_of_each_preset(template, expected):
    assert preview_name(template, "mp3") == expected


def test_preview_uses_given_extension():
    assert preview_name(DEFAULT_TEMPLATE, "wav") == "Название ролика.wav"
    assert preview_name(DEFAULT_TEMPLATE, "webm") == "Название ролика.webm"


def test_preview_plain_date_and_percent_escape():
    assert preview_name("%(upload_date)s %(title)s.%(ext)s", "mp4") == "20261008 Название ролика.mp4"
    assert preview_name("100%% %(title)s.%(ext)s", "mp4") == "100% Название ролика.mp4"
    assert preview_name("%%(title)s.%(ext)s", "mp4") == "%(title)s.mp4"


def test_preview_leaves_unknown_tokens_and_stray_percent():
    assert preview_name("%(foo)s - %(title)s.%(ext)s", "mp3") == "%(foo)s - Название ролика.mp3"
    assert preview_name("50% %(title)s.%(ext)s", "mp3") == "50% Название ролика.mp3"
    assert preview_name("%(upload_date>%H)s.%(ext)s", "mp3") == "00.mp3"
    assert preview_name("%(foo>%Y)s.%(ext)s", "mp3") == "%(foo>%Y)s.mp3"


def test_preview_playlist_prefix_matches_command_builder():
    assert preview_name(DEFAULT_TEMPLATE, "mp3", playlist=True) == "03 - Название ролика.mp3"
    assert playlist_template(DEFAULT_TEMPLATE).startswith("%(playlist_index)s - ")
    # номер уже есть в шаблоне: ничего не добавляется
    assert preview_name("%(playlist_index)s. %(title)s.%(ext)s", "mp3", playlist=True) == "03. Название ролика.mp3"
    assert preview_name(DEFAULT_TEMPLATE, "mp3", playlist=False) == "Название ролика.mp3"


def test_preview_numeric_playlist_index_is_zero_padded():
    assert preview_name("%(playlist_index)03d %(title)s.%(ext)s", "mp3") == "003 Название ролика.mp3"
    assert preview_name("%(playlist_index)d %(title)s.%(ext)s", "mp3", playlist=True) == "3 Название ролика.mp3"


def test_preview_numeric_format_of_text_field_is_left_as_is():
    assert preview_name("%(title)d.%(ext)s", "mp3") == "%(title)d.mp3"


def test_preview_truncation_format():
    assert preview_name("%(title).5s.%(ext)s", "mp3") == "Назва.mp3"
