import os
import shutil
import sys
from pathlib import Path

from ytgui.core import paths


def make_exec(directory: Path, name: str, mode: int = 0o755) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    file = directory / name
    file.write_text("#!/bin/sh\n")
    file.chmod(mode)
    return file


def test_find_tool_prefers_extra_dirs(tmp_path, monkeypatch):
    mine = make_exec(tmp_path / "bin", "yt-dlp")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/other")
    assert paths.find_tool("yt-dlp", [str(tmp_path / "bin")]) == str(mine)


def test_find_tool_skips_non_executable(tmp_path, monkeypatch):
    make_exec(tmp_path / "bin", "ffmpeg", mode=0o644)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert paths.find_tool("ffmpeg", [str(tmp_path / "bin")]) == "/usr/bin/ffmpeg"


def test_find_tool_falls_back_to_system_dirs(tmp_path, monkeypatch):
    sysdir = tmp_path / "homebrew"
    tool = make_exec(sysdir, "ffmpeg")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(paths, "SYSTEM_DIRS", (str(sysdir),))
    assert paths.find_tool("ffmpeg", []) == str(tool)


def test_find_tool_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(paths, "SYSTEM_DIRS", (str(tmp_path / "none"),))
    assert paths.find_tool("nothing", []) is None


def test_bundled_dir_in_development_points_to_packaging_bin():
    assert paths.bundled_dir().endswith(os.path.join("packaging", "bin"))


def test_bundled_dir_when_frozen(monkeypatch, tmp_path):
    exe = tmp_path / "App.app" / "Contents" / "MacOS" / "App"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    expected = (tmp_path / "App.app" / "Contents" / "Resources" / "bin").resolve()
    assert Path(paths.bundled_dir()) == expected


def test_unique_stem_free_name_unchanged(tmp_path):
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song"


def test_unique_stem_adds_numeric_suffix(tmp_path):
    (tmp_path / "Song.mp3").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song (1)"
    (tmp_path / "Song (1).mp3").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song (2)"


def test_unique_stem_only_same_extension_counts(tmp_path):
    (tmp_path / "Song.mp4").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song"


def test_unique_stem_with_special_and_cyrillic_names(tmp_path):
    name = "100% Любовь [Official]"
    (tmp_path / f"{name}.mp3").write_text("")
    assert paths.unique_stem(str(tmp_path), name, "mp3") == f"{name} (1)"


def test_unique_stem_missing_folder_is_free(tmp_path):
    assert paths.unique_stem(str(tmp_path / "нет"), "Song", "mp3") == "Song"


def test_unique_stem_also_extensions_collide(tmp_path):
    (tmp_path / "Song.webm").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3") == "Song"
    assert paths.unique_stem(str(tmp_path), "Song", "mp3", also=("webm", "m4a")) == "Song (1)"
    (tmp_path / "Song (1).m4a").write_text("")
    assert paths.unique_stem(str(tmp_path), "Song", "mp3", also=("webm", "m4a")) == "Song (2)"
