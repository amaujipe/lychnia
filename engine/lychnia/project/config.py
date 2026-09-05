"""`project.toml`: the single source of truth per sermon (spec §8.1).

Parameters live here; derived values (end, duration, frame count, fingerprints)
are properties. Validation errors come out as `ConfigError` with an i18n key.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from lychnia.errors import ConfigError
from lychnia.media.grid import f30, frames_for

VF_DEFAULT_A = "scale=1920:1080:flags=bicubic,setsar=1"
VF_DEFAULT_B = "scale=1920:1080:flags=bicubic,unsharp=5:5:0.3,setsar=1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(_Model):
    date: str = ""
    slug: str = ""
    title: str = ""
    passage: str = ""
    preacher: str = ""
    author_id: str = ""


class Sources(_Model):
    master: str = ""
    cam_a: str = ""
    cam_b: str = ""


class Sync(_Model):
    offset_a: float = 0.0
    offset_b: float = 0.0
    audio_delay_ms: int = 0

    @field_validator("audio_delay_ms")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("validation.audio_delay_negative")
        return v


class Cut(_Model):
    start: float
    end: float

    @model_validator(mode="after")
    def _ordered(self) -> "Cut":
        if self.end <= self.start:
            raise ValueError("validation.cut_end_before_start")
        return self


class Video(_Model):
    vf_a: str = VF_DEFAULT_A
    vf_b: str = VF_DEFAULT_B


class Audio(_Model):
    downmix: Literal["dual-mono", "left", "right"] = "dual-mono"
    lufs: float = -15.0


class GateB(_Model):
    start: float | None = None
    duration: float = 65.0


class Short(_Model):
    id: str
    start: float
    end: float
    keyword: str
    title: str

    @model_validator(mode="after")
    def _ordered(self) -> "Short":
        if self.end <= self.start:
            raise ValueError(f"validation.short_end_before_start|id={self.id}")
        return self


class Phase(_Model):
    start: float
    end: float
    cam: Literal["A", "B"]
    long_shot: float
    rest_shot: float = 0.0
    note: str = ""


class Plan(_Model):
    closing_a: float = 26.0
    phases: list[Phase] = Field(default_factory=list)


class Thumbnail(_Model):
    headline: str | list[str] = ""
    subtitle: str = ""
    mode: Literal["light", "dark"] = "light"
    with_face: bool = False
    ai_background: bool = True


class Publishing(_Model):
    thumbnail_url: str = ""
    youtube_id: str = ""


class ProjectConfig(_Model):
    meta: Meta = Field(default_factory=Meta)
    sources: Sources = Field(default_factory=Sources)
    sync: Sync = Field(default_factory=Sync)
    cut: Cut | None = None
    video: Video = Field(default_factory=Video)
    audio: Audio = Field(default_factory=Audio)
    gate_b: GateB = Field(default_factory=GateB)
    shorts: list[Short] = Field(default_factory=list)
    shorts_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)
    plan: Plan = Field(default_factory=Plan)
    thumbnail: Thumbnail = Field(default_factory=Thumbnail)
    publishing: Publishing = Field(default_factory=Publishing)
    master_limit: float | None = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _empty_cut_is_absent(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("cut") == {}:
            data = {**data, "cut": None}
        return data

    @model_validator(mode="after")
    def _phases_match_the_cut(self) -> "ProjectConfig":
        phases = self.plan.phases
        if not phases:
            return self
        for a, b in zip(phases, phases[1:]):
            if abs(a.end - b.start) > 1e-6:
                raise ValueError(f"validation.phases_gap|end={a.end}|start={b.start}")
        if self.cut is not None:
            if abs(phases[0].start - self.cut.start) > 1e-6:
                raise ValueError(f"validation.phases_start_mismatch|phase={phases[0].start}|cut={self.cut.start}")
            if abs(phases[-1].end - self.cut.end) > 1e-6:
                raise ValueError(f"validation.phases_end_mismatch|phase={phases[-1].end}|cut={self.cut.end}")
        return self

    # ── derived values (never configured) ──────────────────────────────────
    def require_cut(self) -> Cut:
        if self.cut is None:
            raise ConfigError("cut", "validation.cut_missing")
        return self.cut

    @property
    def end(self) -> float:
        """Cut end; when MASTER_LIMIT bounds it, the bound is snapped to the frame grid."""
        cut = self.require_cut()
        if self.master_limit is None:
            return cut.end
        end = f30(min(cut.end, self.master_limit))
        if end <= cut.start:
            raise ConfigError("cut", "validation.master_limit_before_cut",
                              limit=self.master_limit, start=cut.start)
        return end

    @property
    def duration(self) -> float:
        return round(self.end - self.require_cut().start, 6)

    @property
    def frame_count(self) -> int:
        return frames_for(self.duration)

    @property
    def cut_fingerprint(self) -> str:
        return f"{self.require_cut().start}|{self.end}"

    @property
    def video_fingerprint(self) -> str:
        s, v, y = self.sources, self.video, self.sync
        return "|".join(str(x) for x in [s.cam_a, s.cam_b, y.offset_a, y.offset_b, v.vf_a, v.vf_b,
                                         self.require_cut().start, self.end, f"limit={self.master_limit}"])

    @property
    def audio_fingerprint(self) -> str:
        return "|".join(str(x) for x in [self.sources.master, self.audio.downmix, self.audio.lufs,
                                         self.sync.audio_delay_ms, self.require_cut().start, self.end,
                                         f"limit={self.master_limit}"])

    def gate_b_window(self) -> tuple[float, float]:
        start = self.gate_b.start if self.gate_b.start is not None else self.require_cut().start + 60.0
        return float(start), float(self.gate_b.duration)

    def has_input(self, dotted: str) -> bool:
        """True when the config section/field named by `dotted` is filled in."""
        value: Any = self
        for part in dotted.split("."):
            if isinstance(value, BaseModel) and part in type(value).model_fields:
                value = getattr(value, part)
            else:
                return False
        if value is None or value == "" or value == [] or value == {}:
            return False
        return True


# ── loading ────────────────────────────────────────────────────────────────
def _convert(exc: PydanticValidationError) -> ConfigError:
    err = exc.errors()[0]
    field = ".".join(str(p) for p in err["loc"] if p != "master_limit")
    kind = err["type"]
    if kind == "value_error":
        # validators raise ValueError("key|param=value|...")
        key, *pairs = err["msg"].removeprefix("Value error, ").split("|")
        params = dict(p.split("=", 1) for p in pairs)
        section = field.split(".")[0] if field else key.split(".")[-1].split("_")[0]
        return ConfigError(field or section, key, **params)
    if kind == "missing":
        return ConfigError(field, "validation.missing_field")
    if kind == "extra_forbidden":
        return ConfigError(field, "validation.unknown_field")
    return ConfigError(field, "validation.invalid_value", value=err.get("input"))


def parse_config(data: dict, master_limit: float | None = None) -> ProjectConfig:
    try:
        return ProjectConfig.model_validate({**data, "master_limit": master_limit})
    except PydanticValidationError as exc:
        raise _convert(exc) from exc


def load_config(path: Path, master_limit: float | None = None) -> ProjectConfig:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("project.toml", "validation.config_unreadable", detail=str(exc)) from exc
    return parse_config(data, master_limit)
