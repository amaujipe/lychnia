import pytest

from lychnia.errors import ConfigError
from lychnia.project.config_edit import patch_config, read_raw

ORIGINAL = """# header comment
[meta]                              # written once
date = "2026-09-06"                 # YYYY-MM-DD
slug = "prueba"

[sources]
master = "input/audio/m.mkv"        # the good audio

[cut]                               # Gate A decision
start = 100.0                       # where it starts
end   = 200.0
"""


def _write(tmp_path):
    p = tmp_path / "project.toml"
    p.write_text(ORIGINAL, encoding="utf-8")
    return p


def test_patch_changes_value_and_keeps_comments(tmp_path):
    p = _write(tmp_path)
    cfg = patch_config(p, {"cut": {"start": 120.5}})
    assert cfg.cut.start == 120.5
    text = read_raw(p)
    assert "# header comment" in text
    assert "# where it starts" in text
    assert "# Gate A decision" in text
    assert "start = 120.5" in text
    assert 'master = "input/audio/m.mkv"        # the good audio' in text


def test_patch_adds_missing_section_and_key(tmp_path):
    p = _write(tmp_path)
    cfg = patch_config(p, {"audio": {"downmix": "left"}, "meta": {"title": "T"}})
    assert cfg.audio.downmix == "left"
    assert cfg.meta.title == "T"
    assert "[audio]" in read_raw(p)


def test_invalid_patch_leaves_the_file_untouched(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ConfigError) as exc:
        patch_config(p, {"cut": {"end": 50.0}})
    assert exc.value.key == "validation.cut_end_before_start"
    assert read_raw(p) == ORIGINAL
    assert not (tmp_path / "project.toml.partial").exists()
