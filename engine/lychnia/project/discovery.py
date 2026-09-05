"""Find the master and camera files under input/ (what `cfg.py --init` did)."""
from __future__ import annotations

from pathlib import Path

from lychnia.project.layout import ProjectPaths

MEDIA_SUFFIXES = {".mkv", ".mp4", ".mov", ".wav", ".m4a", ".mp3", ".flac"}


def first_media(folder: Path, root: Path) -> str:
    if not folder.is_dir():
        return ""
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES)
    return files[0].relative_to(root).as_posix() if files else ""


def discover_sources(paths: ProjectPaths) -> dict[str, str]:
    return {
        "master": first_media(paths.audio, paths.root),
        "cam_a": first_media(paths.cam_wide, paths.root),
        "cam_b": first_media(paths.cam_preacher, paths.root),
    }
