import re
import subprocess
import sys
from pathlib import Path

import ytgui

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_semantic():
    assert re.fullmatch(r"\d+\.\d+\.\d+", ytgui.__version__)


def test_cli_version_flag_prints_name_and_version():
    result = subprocess.run(
        [sys.executable, "-m", "ytgui", "--version"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"YT Загрузчик {ytgui.__version__}"


def test_build_script_writes_version_into_bundle_plist():
    script = (ROOT / "packaging" / "build_app.sh").read_text(encoding="utf-8")
    assert "CFBundleShortVersionString" in script and "CFBundleVersion" in script
    assert "ytgui import __version__" in script
