"""Folder layout of a sermon project (spec §3)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def config_file(self) -> Path: return self.root / "project.toml"
    @property
    def input(self) -> Path: return self.root / "input"
    @property
    def audio(self) -> Path: return self.input / "audio"
    @property
    def cam_wide(self) -> Path: return self.input / "cam-wide"
    @property
    def cam_preacher(self) -> Path: return self.input / "cam-preacher"
    @property
    def photos(self) -> Path: return self.input / "photos"
    @property
    def info_md(self) -> Path: return self.input / "INFO.md"
    @property
    def transcript(self) -> Path: return self.root / "transcript"
    @property
    def outline(self) -> Path: return self.root / "outline"
    @property
    def video(self) -> Path: return self.root / "video"
    @property
    def video_work(self) -> Path: return self.video / "work"
    @property
    def gate_a(self) -> Path: return self.video / "gate_a"
    @property
    def gate_b(self) -> Path: return self.video / "gate_b"
    @property
    def shorts(self) -> Path: return self.video / "shorts"
    @property
    def youtube(self) -> Path: return self.root / "youtube"
    @property
    def youtube_assets(self) -> Path: return self.youtube / "assets"
    @property
    def blog(self) -> Path: return self.root / "blog"
    @property
    def blog_images(self) -> Path: return self.blog / "images"
    @property
    def state_dir(self) -> Path: return self.root / ".lychnia"
    @property
    def state_db(self) -> Path: return self.state_dir / "state.sqlite"
    @property
    def logs(self) -> Path: return self.state_dir / "logs"

    def all_dirs(self) -> list[Path]:
        return [self.audio, self.cam_wide, self.cam_preacher, self.photos, self.transcript,
                self.outline, self.video_work, self.gate_a, self.gate_b, self.shorts,
                self.youtube_assets, self.blog_images, self.logs]

    def ensure(self) -> None:
        for d in self.all_dirs():
            d.mkdir(parents=True, exist_ok=True)
