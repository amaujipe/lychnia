from lychnia.project.discovery import discover_sources
from lychnia.project.layout import ProjectPaths


def test_paths_follow_the_spec_layout(tmp_path):
    p = ProjectPaths(tmp_path / "2026-09-06_prueba")
    root = p.root
    assert p.config_file == root / "project.toml"
    assert p.audio == root / "input" / "audio"
    assert p.cam_wide == root / "input" / "cam-wide"
    assert p.cam_preacher == root / "input" / "cam-preacher"
    assert p.info_md == root / "input" / "INFO.md"
    assert p.video_work == root / "video" / "work"
    assert p.gate_b == root / "video" / "gate_b"
    assert p.shorts == root / "video" / "shorts"
    assert p.youtube_assets == root / "youtube" / "assets"
    assert p.blog_images == root / "blog" / "images"
    assert p.state_db == root / ".lychnia" / "state.sqlite"
    assert p.logs == root / ".lychnia" / "logs"


def test_ensure_creates_every_directory(tmp_path):
    p = ProjectPaths(tmp_path / "proj")
    p.ensure()
    for d in p.all_dirs():
        assert d.is_dir(), d


def test_discover_sources_picks_the_first_media_file(tmp_path):
    p = ProjectPaths(tmp_path / "proj")
    p.ensure()
    (p.audio / "2026-09-06 09-41-53.mkv").write_bytes(b"")
    (p.audio / "notes.txt").write_bytes(b"")
    (p.cam_wide / "b.mkv").write_bytes(b"")
    (p.cam_wide / "a.mp4").write_bytes(b"")
    assert discover_sources(p) == {
        "master": "input/audio/2026-09-06 09-41-53.mkv",
        "cam_a": "input/cam-wide/a.mp4",
        "cam_b": "",
    }
