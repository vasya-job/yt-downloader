import json

from ytgui.core.settings import Settings, load, save, settings_path


def test_default_path_is_in_application_support():
    p = settings_path()
    assert p.name == "settings.json"
    assert "Application Support" in str(p)


def test_roundtrip_with_cyrillic_folder(tmp_path):
    target = tmp_path / "s.json"
    original = Settings(
        folder="/Users/я/Музыка", mode="video", audio_format="opus", audio_quality=3,
        video_format="webm", max_height=720, template="%(uploader)s - %(title)s.%(ext)s",
        cookies_browser="firefox", open_folder=False,
    )
    save(original, target)
    assert load(target) == original
    assert "Музыка" in target.read_text(encoding="utf-8")


def test_missing_file_gives_defaults(tmp_path):
    assert load(tmp_path / "нет.json") == Settings()


def test_corrupt_json_gives_defaults(tmp_path):
    target = tmp_path / "s.json"
    target.write_text("{не json", encoding="utf-8")
    assert load(target) == Settings()


def test_empty_file_gives_defaults(tmp_path):
    target = tmp_path / "s.json"
    target.write_text("", encoding="utf-8")
    assert load(target) == Settings()


def test_non_object_json_gives_defaults(tmp_path):
    target = tmp_path / "s.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    assert load(target) == Settings()


def test_wrong_types_and_ranges_fall_back_per_field(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(
        json.dumps({
            "folder": "/ok", "audio_quality": "лучшее", "mode": "radio",
            "audio_format": "flac", "max_height": 360, "open_folder": "yes",
            "cookies_browser": "safari", "template": "  ",
        }),
        encoding="utf-8",
    )
    s = load(target)
    assert s.folder == "/ok"
    assert s == Settings(folder="/ok")


def test_bool_is_not_a_valid_quality(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"audio_quality": True}), encoding="utf-8")
    assert load(target).audio_quality == 0


def test_quality_out_of_range_falls_back(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"audio_quality": 99}), encoding="utf-8")
    assert load(target).audio_quality == 0


def test_unknown_keys_are_ignored(tmp_path):
    target = tmp_path / "s.json"
    target.write_text(json.dumps({"folder": "/a", "future_option": 1}), encoding="utf-8")
    assert load(target) == Settings(folder="/a")


def test_save_creates_parent_directories(tmp_path):
    target = tmp_path / "a" / "b" / "s.json"
    save(Settings(folder="/x"), target)
    assert load(target).folder == "/x"
    assert not (tmp_path / "a" / "b" / "s.tmp").exists()


def test_load_when_parent_is_a_file_gives_defaults(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert load(blocker / "s.json") == Settings()
