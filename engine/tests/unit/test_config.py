import pytest

from lychnia.errors import ConfigError
from lychnia.project.config import VF_DEFAULT_A, VF_DEFAULT_B, load_config, parse_config

MINIMAL = {
    "meta": {"date": "2026-09-06", "slug": "prueba"},
    "sources": {"master": "input/audio/m.mkv", "cam_a": "input/cam-wide/a.mkv", "cam_b": ""},
    "sync": {"offset_a": -0.333, "offset_b": -0.6},
    "cut": {"start": 557.5, "end": 5242.5},
    "audio": {"downmix": "dual-mono", "lufs": -15},
}


def test_derived_values():
    cfg = parse_config(MINIMAL)
    assert cfg.end == 5242.5
    assert cfg.duration == 4685.0
    assert cfg.frame_count == 140550
    assert cfg.cut_fingerprint == "557.5|5242.5"
    assert cfg.video.vf_a == VF_DEFAULT_A and cfg.video.vf_b == VF_DEFAULT_B


def test_master_limit_bounds_the_end_on_the_grid():
    cfg = parse_config(MINIMAL, master_limit=700)
    assert cfg.end == 700.0
    assert cfg.duration == 142.5
    assert cfg.frame_count == 4275
    assert cfg.cut_fingerprint == "557.5|700.0"
    assert "limit=700" in cfg.video_fingerprint


def test_master_limit_before_cut_start_is_an_error():
    cfg = parse_config(MINIMAL, master_limit=100)
    with pytest.raises(ConfigError) as exc:
        _ = cfg.end
    assert exc.value.key == "validation.master_limit_before_cut"


def test_fingerprints_change_only_with_their_fields():
    base = parse_config(MINIMAL)
    with_short = parse_config({**MINIMAL, "shorts": [
        {"id": "s1", "start": 10, "end": 40, "keyword": "x", "title": "t"}]})
    assert with_short.video_fingerprint == base.video_fingerprint
    assert with_short.audio_fingerprint == base.audio_fingerprint
    louder = parse_config({**MINIMAL, "audio": {"downmix": "left", "lufs": -16}})
    assert louder.audio_fingerprint != base.audio_fingerprint
    assert louder.video_fingerprint == base.video_fingerprint


def test_cut_end_before_start():
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "cut": {"start": 10, "end": 5}})
    assert exc.value.key == "validation.cut_end_before_start"
    assert exc.value.field == "cut"


def test_negative_audio_delay():
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "sync": {"audio_delay_ms": -5}})
    assert exc.value.key == "validation.audio_delay_negative"
    assert exc.value.field == "sync.audio_delay_ms"


def test_unknown_field_and_bad_downmix():
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "audio": {"mezcla": "dual-mono"}})
    assert exc.value.key == "validation.unknown_field"
    assert exc.value.field == "audio.mezcla"
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "audio": {"downmix": "stereo"}})
    assert exc.value.key == "validation.invalid_value"


def test_missing_cut_loads_but_derived_values_fail():
    data = {k: v for k, v in MINIMAL.items() if k != "cut"}
    cfg = parse_config(data)
    assert cfg.cut is None
    assert not cfg.has_input("cut")
    with pytest.raises(ConfigError) as exc:
        _ = cfg.duration
    assert exc.value.key == "validation.cut_missing"
    empty_table = parse_config({**data, "cut": {}})
    assert empty_table.cut is None


def test_has_input_dotted_paths():
    cfg = parse_config(MINIMAL)
    assert cfg.has_input("cut")
    assert cfg.has_input("sources.master")
    assert not cfg.has_input("sources.cam_b")
    assert not cfg.has_input("plan.phases")
    assert not cfg.has_input("shorts")
    assert not cfg.has_input("publishing.thumbnail_url")
    assert not cfg.has_input("does.not.exist")


def test_phases_must_be_contiguous_and_aligned_to_the_cut():
    ok = parse_config({**MINIMAL, "plan": {"closing_a": 26.0, "phases": [
        {"start": 557.5, "end": 600.0, "cam": "A", "long_shot": 12.5},
        {"start": 600.0, "end": 5242.5, "cam": "B", "long_shot": 86.0, "rest_shot": 18.0},
    ]}})
    assert len(ok.plan.phases) == 2 and ok.has_input("plan.phases")
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "plan": {"phases": [
            {"start": 557.5, "end": 600.0, "cam": "A", "long_shot": 12.5},
            {"start": 601.0, "end": 5242.5, "cam": "B", "long_shot": 86.0},
        ]}})
    assert exc.value.key == "validation.phases_gap"
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "plan": {"phases": [
            {"start": 500.0, "end": 5242.5, "cam": "B", "long_shot": 86.0}]}})
    assert exc.value.key == "validation.phases_start_mismatch"


def test_short_end_before_start():
    with pytest.raises(ConfigError) as exc:
        parse_config({**MINIMAL, "shorts": [
            {"id": "s1", "start": 40, "end": 10, "keyword": "x", "title": "t"}]})
    assert exc.value.key == "validation.short_end_before_start"
    assert exc.value.params["id"] == "s1"


def test_gate_b_defaults_to_one_minute_after_the_cut():
    cfg = parse_config(MINIMAL)
    assert cfg.gate_b_window() == (617.5, 65.0)
    cfg2 = parse_config({**MINIMAL, "gate_b": {"start": 3021, "duration": 65}})
    assert cfg2.gate_b_window() == (3021.0, 65.0)


def test_load_config_reads_toml(tmp_path):
    p = tmp_path / "project.toml"
    p.write_text('[cut]\nstart = 1.0\nend = 2.0\n[sources]\nmaster = "input/audio/m.mkv"\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.duration == 1.0


def test_load_config_unreadable(tmp_path):
    p = tmp_path / "project.toml"
    p.write_text("[cut\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(p)
    assert exc.value.key == "validation.config_unreadable"
