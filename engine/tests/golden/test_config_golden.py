from tests.golden.legacy import LEGACY_ARTIFACTS, load_legacy_config


def test_2026_08_30_config_through_the_legacy_adapter(fixture_dir):
    cfg = load_legacy_config(fixture_dir / "proyecto.toml")
    assert cfg.meta.slug == "gracia-que-produce-excelencia"
    assert cfg.meta.passage == "Génesis 8"
    assert cfg.meta.author_id == "seniorPastor"
    assert cfg.sources.master.endswith("2026-08-30 09-41-53.mkv")
    assert cfg.sources.cam_b.endswith("_Pastor.mkv")
    assert (cfg.sync.offset_a, cfg.sync.offset_b, cfg.sync.audio_delay_ms) == (-0.333, -0.6, 0)
    assert cfg.cut_fingerprint == "557.5|5242.5"
    assert cfg.duration == 4685.0
    assert cfg.frame_count == 140550
    assert cfg.audio.downmix == "dual-mono" and cfg.audio.lufs == -15
    assert cfg.gate_b_window() == (3021.0, 65.0)
    assert [s.id for s in cfg.shorts] == ["s1-logico-o-biblico", "s2-espera-su-voz",
                                          "s3-dios-en-la-lluvia", "s4-corazon-sano", "s5-ayudas-que-lastiman"]
    assert cfg.shorts_overrides["s3-dios-en-la-lluvia"]["-1"].startswith("A Dios en medio de la lluvia")
    assert len(cfg.plan.phases) == 9
    assert cfg.plan.closing_a == 26.0
    assert cfg.plan.phases[1].cam == "B" and cfg.plan.phases[1].long_shot == 58.0
    assert cfg.plan.phases[1].rest_shot == 14.0


def test_legacy_config_with_master_limit(fixture_dir):
    cfg = load_legacy_config(fixture_dir / "proyecto.toml", master_limit=700)
    assert cfg.duration == 142.5 and cfg.frame_count == 4275


def test_legacy_artifact_files_exist(fixture_dir):
    for logical, filename in LEGACY_ARTIFACTS.items():
        assert (fixture_dir / filename).exists(), logical
