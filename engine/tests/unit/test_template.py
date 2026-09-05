import tomllib

from lychnia.project.config import load_config
from lychnia.project.layout import ProjectPaths
from lychnia.project.template import create_project, render_project_toml


def test_rendered_template_parses_and_has_comments():
    text = render_project_toml("2026-09-06", "prueba", {"master": "input/audio/m.mkv", "cam_a": "", "cam_b": ""}, lang="en")
    data = tomllib.loads(text)
    assert data["meta"] == {"date": "2026-09-06", "slug": "prueba", "title": "", "passage": "",
                            "preacher": "", "author_id": ""}
    assert data["sources"]["master"] == "input/audio/m.mkv"
    assert "cut" not in data or data["cut"] == {}
    assert text.count("#") > 15            # the template is documentation for the operator
    assert "[[plan.phases]]" in text        # commented example block
    assert "[[shorts]]" in text


def test_rendered_template_is_localized():
    es = render_project_toml("2026-09-06", "p", {"master": "", "cam_a": "", "cam_b": ""}, lang="es")
    en = render_project_toml("2026-09-06", "p", {"master": "", "cam_a": "", "cam_b": ""}, lang="en")
    assert es != en
    assert tomllib.loads(es) == tomllib.loads(en)   # same data, different comments


def test_create_project_builds_folder_and_discovers_sources(tmp_path):
    folder = create_project(tmp_path, "2026-09-06", "prueba", lang="es")
    assert folder == tmp_path / "2026-09-06_prueba"
    paths = ProjectPaths(folder)
    assert paths.config_file.exists() and paths.info_md.exists()
    cfg = load_config(paths.config_file)
    assert cfg.meta.date == "2026-09-06" and cfg.meta.slug == "prueba"
    assert cfg.cut is None
    # second run with media present fills the sources, because the TOML still has none
    (paths.audio / "m.mkv").write_bytes(b"")
    create_project(tmp_path, "2026-09-06", "prueba", lang="es")
    assert load_config(paths.config_file).sources.master == "input/audio/m.mkv"
    # a TOML that already has sources is never touched
    paths.config_file.write_text(paths.config_file.read_text(encoding="utf-8").replace("m.mkv", "keep.mkv"),
                                 encoding="utf-8")
    create_project(tmp_path, "2026-09-06", "prueba", lang="es")
    assert load_config(paths.config_file).sources.master == "input/audio/keep.mkv"
