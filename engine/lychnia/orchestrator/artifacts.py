"""Logical artifact names and where they live inside a project (spec §4, §5)."""
from __future__ import annotations

from dataclasses import dataclass

SOURCE_PREFIX = "source:"
CONFIG_PREFIX = "config:"


def is_source(name: str) -> bool:
    return name.startswith(SOURCE_PREFIX)


def is_config(name: str) -> bool:
    return name.startswith(CONFIG_PREFIX)


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: str                 # relative to the project root; may contain {slug}
    providable: bool = False  # a person (or the Writer) supplies it; no task produces it


ARTIFACTS: dict[str, ArtifactSpec] = {a.name: a for a in [
    ArtifactSpec("transcript.srt", "transcript/transcript.srt"),
    ArtifactSpec("transcript.tsv", "transcript/transcript.tsv"),
    ArtifactSpec("transcript.txt", "transcript/transcript.txt"),
    ArtifactSpec("transcript.vtt", "transcript/transcript.vtt"),
    ArtifactSpec("transcript.json", "transcript/transcript.json"),
    ArtifactSpec("camera_health.txt", "transcript/camera_health.txt"),
    ArtifactSpec("silences.raw.txt", "video/work/silences.raw.txt"),
    ArtifactSpec("camera_plan.json", "outline/camera_plan.json"),
    ArtifactSpec("outline.md", "outline/outline.md", providable=True),
    ArtifactSpec("callouts.toml", "outline/callouts.toml", providable=True),
    ArtifactSpec("callouts.ass", "outline/callouts.ass"),
    ArtifactSpec("callouts_render.ass", "outline/callouts_render.ass"),
    ArtifactSpec("control_sheets.txt", "video/gate_a/control_sheets.txt"),
    ArtifactSpec("segments.txt", "video/work/segments.txt"),
    ArtifactSpec("preview.mp4", "video/gate_b/preview.mp4"),
    ArtifactSpec("final.mp4", "video/final.mp4"),
    ArtifactSpec("final.srt", "video/final.srt"),
    ArtifactSpec("shorts.txt", "video/shorts/shorts.txt"),
    ArtifactSpec("background.png", "youtube/assets/background.png", providable=True),
    ArtifactSpec("background-prompt.md", "youtube/assets/background-prompt.md", providable=True),
    ArtifactSpec("thumbnail.jpg", "youtube/thumbnail.jpg"),
    ArtifactSpec("thumbnail-1280.jpg", "youtube/thumbnail-1280.jpg"),
    ArtifactSpec("youtube.md", "youtube/youtube.md", providable=True),
    ArtifactSpec("shorts-metadata.md", "youtube/shorts-metadata.md", providable=True),
    ArtifactSpec("blog.src.mdx", "blog/{slug}.src.mdx", providable=True),
    ArtifactSpec("blog.mdx", "blog/{slug}.mdx"),
]}
