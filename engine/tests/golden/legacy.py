"""Adapter for the 2026-08-30 fixtures written by the original pipeline (Spanish keys).

Production code never reads Spanish keys; only the golden tests do, through here.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from lychnia.project.config import ProjectConfig, parse_config

LEGACY_ARTIFACTS: dict[str, str] = {
    "transcript.srt": "predica.srt",
    "transcript.tsv": "predica.tsv",
    "callouts.toml": "callouts.toml",
    "silences.raw.txt": "silencios.raw.txt",
    "expected.camera_plan.json": "esperado_plan_camaras.json",
    "expected.callouts.ass": "esperado_callouts.ass",
    "expected.callouts_render.ass": "esperado_callouts_render.ass",
}

_DOWNMIX = {"dual-mono": "dual-mono", "izquierdo": "left", "derecho": "right"}


def _rename(d: dict, mapping: dict[str, str]) -> dict:
    return {mapping.get(k, k): v for k, v in d.items()}


def legacy_to_config_dict(data: dict) -> dict:
    out: dict = {}
    if "meta" in data:
        out["meta"] = _rename(data["meta"], {"fecha": "date", "titulo": "title", "pasaje": "passage",
                                             "pastor": "preacher", "autor_id": "author_id"})
    if "fuentes" in data:
        out["sources"] = _rename(data["fuentes"], {"maestro": "master"})
    if "sync" in data:
        out["sync"] = _rename(data["sync"], {"off_a": "offset_a", "off_b": "offset_b"})
    if "corte" in data:
        out["cut"] = _rename(data["corte"], {"entrada": "start", "salida": "end"})
    if "video" in data:
        out["video"] = dict(data["video"])
    if "audio" in data:
        audio = _rename(data["audio"], {"mezcla": "downmix"})
        if "downmix" in audio:
            audio["downmix"] = _DOWNMIX[audio["downmix"]]
        out["audio"] = audio
    if "gate_b" in data:
        out["gate_b"] = _rename(data["gate_b"], {"inicio": "start", "duracion": "duration"})
    if "shorts" in data:
        out["shorts"] = [_rename(s, {"ini": "start", "fin": "end", "clave": "keyword", "titulo": "title"})
                         for s in data["shorts"]]
    if "shorts_overrides" in data:
        out["shorts_overrides"] = {k: dict(v) for k, v in data["shorts_overrides"].items()}
    if "plan" in data:
        plan = _rename(data["plan"], {"cierre_a": "closing_a", "fases": "phases"})
        plan["phases"] = [_rename(f, {"t_ini": "start", "t_fin": "end", "dur_larga": "long_shot",
                                      "dur_descanso": "rest_shot", "nota": "note"})
                          for f in plan.get("phases", [])]
        out["plan"] = plan
    return out


def load_legacy_config(path: Path, master_limit: float | None = None) -> ProjectConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return parse_config(legacy_to_config_dict(data), master_limit)
