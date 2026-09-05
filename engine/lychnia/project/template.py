"""Write a new `project.toml` (comments from i18n) and the INFO.md template."""
from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

import tomlkit

from lychnia.i18n import current_language, t
from lychnia.project.discovery import discover_sources
from lychnia.project.layout import ProjectPaths


def _table(comment_key: str, lang: str, **fields: object) -> tomlkit.items.Table:
    table = tomlkit.table()
    table.comment(t(comment_key, lang))
    for key, value in fields.items():
        table.add(key, value)
    return table


def _annotate(table: tomlkit.items.Table, lang: str, **keys: str) -> None:
    for field, comment_key in keys.items():
        table[field].comment(t(comment_key, lang))


def render_project_toml(date: str, slug: str, sources: dict[str, str], lang: str | None = None) -> str:
    lang = lang or current_language()
    doc = tomlkit.document()
    doc.add(tomlkit.comment(t("template.header", lang)))
    doc.add(tomlkit.nl())

    meta = _table("template.meta", lang, date=date, slug=slug, title="", passage="", preacher="", author_id="")
    _annotate(meta, lang, date="template.meta_date", slug="template.meta_slug", title="template.meta_title",
              passage="template.meta_passage", preacher="template.meta_preacher", author_id="template.meta_author_id")
    doc.add("meta", meta)

    src = _table("template.sources", lang, master=sources.get("master", ""),
                 cam_a=sources.get("cam_a", ""), cam_b=sources.get("cam_b", ""))
    _annotate(src, lang, master="template.sources_master", cam_a="template.sources_cam_a", cam_b="template.sources_cam_b")
    doc.add("sources", src)

    sync = _table("template.sync", lang, offset_a=0.0, offset_b=0.0, audio_delay_ms=0)
    _annotate(sync, lang, audio_delay_ms="template.sync_delay")
    doc.add("sync", sync)

    cut = _table("template.cut", lang)
    cut.add(tomlkit.comment(f"start = 557.5    # {t('template.cut_start', lang)}"))
    cut.add(tomlkit.comment(f"end   = 5242.5   # {t('template.cut_end', lang)}"))
    doc.add("cut", cut)

    video = _table("template.video", lang)
    video.add(tomlkit.comment('vf_a = "scale=1920:1080:flags=bicubic,setsar=1"'))
    video.add(tomlkit.comment('vf_b = "scale=1920:1080:flags=bicubic,unsharp=5:5:0.3,setsar=1"'))
    doc.add("video", video)

    audio = _table("template.audio", lang, downmix="dual-mono", lufs=-15)
    _annotate(audio, lang, downmix="template.audio_downmix", lufs="template.audio_lufs")
    doc.add("audio", audio)

    gate_b = _table("template.gate_b", lang)
    gate_b.add(tomlkit.comment("start    = 3021"))
    gate_b.add(tomlkit.comment("duration = 65"))
    doc.add("gate_b", gate_b)

    doc.add(tomlkit.nl())
    for line in [t("template.shorts", lang), "[[shorts]]", 'id      = "s1-slug"', "start   = 3013.29",
                 "end     = 3055.30", f'keyword = "{t("template.example_short_keyword", lang)}"',
                 f'title   = "{t("template.example_short_title", lang)}"', "",
                 t("template.shorts_overrides", lang), '[shorts_overrides."s1-slug"]',
                 f'"-1" = "{t("template.example_override_text", lang)}"']:
        doc.add(tomlkit.comment(line) if line else tomlkit.nl())

    plan = _table("template.plan", lang, closing_a=26.0)
    _annotate(plan, lang, closing_a="template.plan_closing_a")
    for line in ["[[plan.phases]]", "start     = 557.5", "end       = 570.0", 'cam       = "A"',
                 "long_shot = 12.5", "rest_shot = 0.0",
                 f'note      = "{t("template.example_phase_note", lang)}"']:
        plan.add(tomlkit.comment(line))
    doc.add("plan", plan)

    thumb = _table("template.thumbnail", lang, headline="", subtitle="", mode="light", with_face=False, ai_background=True)
    doc.add("thumbnail", thumb)

    pub = _table("template.publishing", lang, thumbnail_url="", youtube_id="")
    doc.add("publishing", pub)
    return tomlkit.dumps(doc)


def _has_master(config_file: Path) -> bool:
    try:
        data = tomllib.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return bool(data.get("sources", {}).get("master"))


def adopt_project(folder: Path, lang: str | None = None) -> Path:
    """Make an existing folder a Lychnia project: dirs, INFO.md, project.toml with discovered sources.

    A project.toml that already names a master is never touched (`init` semantics).
    """
    lang = lang or current_language()
    paths = ProjectPaths(Path(folder))
    paths.ensure()
    if not paths.info_md.exists():
        info = resources.files("lychnia.resources").joinpath(f"INFO.{lang}.md").read_text(encoding="utf-8")
        paths.info_md.write_text(info, encoding="utf-8")
    if paths.config_file.exists() and _has_master(paths.config_file):
        return paths.root
    date, _, slug = paths.root.name.partition("_")
    paths.config_file.write_text(render_project_toml(date, slug, discover_sources(paths), lang), encoding="utf-8")
    return paths.root


def create_project(root: Path, date: str, slug: str, lang: str | None = None) -> Path:
    return adopt_project(Path(root) / f"{date}_{slug}", lang)
