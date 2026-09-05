from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "golden" / "fixtures" / "2026-08-30"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURES


MINIMAL_TOML = """[meta]
date = "2026-09-06"
slug = "prueba"
[sources]
master = "input/audio/m.mkv"
cam_a = "input/cam-wide/a.mkv"
[cut]
start = 100.0
end = 200.0
"""


@pytest.fixture
def make_project(tmp_path):
    """Create a minimal project folder; returns a factory taking optional toml text."""
    def _make(toml_text: str = MINIMAL_TOML, name: str = "2026-09-06_prueba"):
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        (root / "project.toml").write_text(toml_text, encoding="utf-8")
        return root
    return _make
