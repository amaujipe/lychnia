# Engine Plan 01: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `lychnia` Python package core that every later task plugs into: config model with derived values and fingerprints, i18n, project layout, artifact registry (SQLite), task graph, derived statuses, resource-limited scheduler, ffmpeg runner with progress and cancellation. No media task is migrated yet; everything is unit-tested without ffmpeg or video files, plus one golden test on the 2026-08-30 config.

**Architecture:** One package `engine/lychnia/` (Python 3.12). `project/` reads and edits `project.toml` (pydantic validation, tomlkit for comment-preserving edits). `orchestrator/` holds the task graph, hashes, SQLite state, status derivation, event bus, execution context and a thread-based scheduler with three lanes. `media/ffmpeg.py` wraps ffmpeg with `-progress pipe:1`. Every operator-facing string is an i18n key resolved from `i18n/es.toml` (default) or `en.toml`.

**Tech Stack:** Python 3.12 (mise-pinned), venv + pip, hatchling, pydantic v2, tomlkit, platformdirs, pytest. No uv or poetry (not installed; pick one lockfile-free approach and keep it).

**Spec:** `docs/superpowers/specs/2026-09-04-engine-design.md` (approved 2026-09-04). Glossary: `docs/GLOSSARY.md`. Original scripts (read-only reference): `~/Repositorios/multimedia-iglesia-tunja/recursos/scripts/pipeline/`.

## Plan series for the Engine sub-project

The Engine spec is too large for one plan that keeps every step concrete. It is split into four plans; each leaves the test suite green and adds working, testable software. This document is plan 01.

| Plan | Scope | Delivers |
|---|---|---|
| **01 Foundation** (this) | package, i18n, errors, config + legacy adapter, config editing, hashing, layout/discovery/template, SQLite state, artifacts/task/graph, events/context, status derivation, scheduler, ffmpeg runner, `filter_path` | `pytest` green; golden config test on the 2026-08-30 sermon |
| 02 Text lane | `text/srt.py`, anchoring, `text/ass_style.py`, `text/callouts.py`, tasks `plan`, `callouts`, `subtitles`, `blog`, `init`; assistant `srt.search` | golden tests: 87 shots, `callouts.ass` byte for byte, `final.srt` |
| 03 Media lane | capabilities, encoders, tasks `transcribe` (faster-whisper provider), `camera_health`, `control_frames`, `segments`, `preview`, `render`, `shorts` + `media/tracking.py`, `thumbnail`; sync assistants; providers `WriterManual`, `BibleManual`, `DetectorMedian` | opt-in smoke tests with `MASTER_LIMIT=700` on the `prueba-render` media |
| 04 API + CLI | FastAPI routes, WebSocket events, token file, Typer CLI, Engine config (`platformdirs`), i18n static scan of the whole package, minimal CI workflow | `lychnia serve`, `lychnia status`, `run`, `provide`, `approve`; API tests with `TestClient` |

## Decisions taken while planning (Andrés confirms or overrides)

1. **Four plans, not one.** Reason above. Plan 02 is where the golden tests of the spec land.
2. **Two extra derived states** beyond spec §4.1: `blocked` (all inputs exist but an upstream gated artifact is not approved) and `unregistered` (outputs exist on disk but the registry has no row, the "old project" case of §6.2). Both are needed so the board can say what to do.
3. **Inputs are strings with three prefixes.** Artifacts by logical name (`transcript.srt`), sources as `source:master` / `source:cam_a` / `source:cam_b`, config sections as `config:cut`, `config:plan.phases`, `config:shorts`, `config:publishing.thumbnail_url`. This is how "inputs (artifacts or config sections)" from spec §4 becomes code.
4. **Logical names without the slug:** `blog.src.mdx` and `blog.mdx` (paths still `blog/<slug>.src.mdx`), `control_sheets.txt` (list of the contact sheets) and `shorts.txt` (list of produced shorts) as the registered outputs of directory-producing tasks.
5. **`[cut]` may be absent.** A freshly created `project.toml` has no cut yet; the config still loads and the board shows `missing_input: config:cut` for the tasks that need it. Derived values raise `ConfigError` when the cut is missing.
6. **Golden comparisons normalize line endings.** `esperado_callouts.ass` and `predica.srt` have CRLF (produced on Windows). Tests compare after `.replace("\r\n", "\n")`; the Engine always writes `\n`.
7. **Runner on threads**, one per task, lane semaphores `gpu=1`, `cpu_heavy=1`, `light=4`. FastAPI (plan 04) talks to it through the event bus and the store; no asyncio in the core.
8. **`filter_path` returns a single-quoted, escaped token** (`'C\:/Users/x/callouts.ass'`). Unit-tested as a pure function here; verified against real ffmpeg in plan 03 with a directory named `a:b c`.

## Global Constraints

- Python `>=3.12,<3.13` (PyInstaller packaging target). One codebase for Linux, Windows, macOS.
- `pathlib` everywhere; `subprocess` with argument lists, never `shell=True`; no `os.chdir`; no `sys.path.insert`; no `print` for output; no `sys.exit`; no bare `assert` in production code (exceptions `ConfigError`, `TaskError`).
- Paths inside ffmpeg filters go through `lychnia.media.ffmpeg.filter_path`; `/` separators.
- English identifiers everywhere (glossary in `docs/GLOSSARY.md`). Commits in English, Conventional Commits (`feat(engine): ...`).
- Operator-facing text only through `lychnia.i18n.t(key, ...)`; keys English snake_case, dotted by section; `es.toml` (default, soft voseo: «revisá», «aprobalo») and `en.toml` always have the same key set. Tests assert on keys, never on Spanish text.
- Hashes: files `<= 64 MiB` full SHA-256 (`sha256:<hex>`); larger files size + mtime + SHA-256 of the first and last 8 MiB (`large:<hex>`).
- Frame grid: `FPS = 30`; `f30(t) = round(round(t*30)/30, 6)`.
- Voice chain (hard rule 7): must end with `aresample=48000`.
- Every test file lives under `engine/tests/unit/` unless stated; `pytest` runs from `engine/` with the venv: `cd engine && .venv/bin/pytest`.
- Third-party APIs: before writing code against pydantic, tomlkit or platformdirs, fetch version-exact docs with the `library-docs` skill (Context7). Adding a dependency goes through the `dependency-hygiene` skill (osv-scanner before and after).

## File structure after this plan

```
mise.toml                                  # pins python 3.12.14 for the repo
.gitignore
engine/
├── pyproject.toml
├── lychnia/
│   ├── __init__.py                        # __version__
│   ├── errors.py                          # LychniaError, ConfigError, TaskError, Cancelled
│   ├── i18n/__init__.py, es.toml, en.toml
│   ├── media/grid.py                      # FPS, f30, on_grid, frames_for
│   ├── media/voice_chain.py               # DOWNMIX, voice_filter
│   ├── media/ffmpeg.py                    # run_ffmpeg, parse_progress_line, filter_path
│   ├── project/config.py                  # pydantic models, load_config, parse_config, derived values
│   ├── project/config_edit.py             # patch_config (tomlkit, comments preserved)
│   ├── project/layout.py                  # ProjectPaths
│   ├── project/discovery.py               # discover_sources
│   ├── project/template.py                # render_project_toml, create_project
│   ├── project/project.py                 # Project: config, paths, store, artifact paths and hashes
│   ├── orchestrator/hashing.py            # hash_file
│   ├── orchestrator/state.py              # StateStore (sqlite3, WAL)
│   ├── orchestrator/artifacts.py          # ArtifactSpec, ARTIFACTS
│   ├── orchestrator/task.py               # Task, Resource, Gate
│   ├── orchestrator/graph.py              # TaskGraph, TARGETS
│   ├── orchestrator/events.py             # EventBus, Event
│   ├── orchestrator/context.py            # Context (log, progress, outputs, cancellation)
│   ├── orchestrator/status.py             # State, TaskStatus, derive_status, status_board, full_fingerprint
│   ├── orchestrator/scheduler.py          # Scheduler, LANE_CAPACITY, RunReport
│   └── resources/INFO.es.md, INFO.en.md
└── tests/
    ├── conftest.py                        # fixture_dir, make_project
    ├── unit/test_*.py
    └── golden/legacy.py, test_config_golden.py, fixtures/2026-08-30/ (exists)
```

Core signatures other tasks rely on (defined in the task that creates them, repeated here for orientation):

```python
# errors
class LychniaError(Exception): key: str; params: dict
class ConfigError(LychniaError): field: str
class TaskError(LychniaError): command: list[str] | None; stderr_tail: str
class Cancelled(LychniaError)
# i18n
def t(key: str, lang: str | None = None, **params) -> str
# config
def load_config(path: Path, master_limit: float | None = None) -> ProjectConfig
def parse_config(data: dict, master_limit: float | None = None) -> ProjectConfig
ProjectConfig.end / .duration / .frame_count / .cut_fingerprint / .video_fingerprint / .audio_fingerprint / .has_input(dotted)
# hashing
def hash_file(path: Path, large_threshold: int = 64 * 2**20) -> str
# state
class StateStore: record_artifact, get_artifact, approve, revoke_approval, mark_edited, start_run, set_run_status, finish_run, latest_run, add_event
# task/graph
class Task: name, inputs, outputs, resource, gate, on_demand, fingerprint(cfg), run(ctx)
class TaskGraph: producer_of(name), dependencies(task), closure(names), resolve_target(target)
# project
class Project: id, root, paths, config, store, artifact_path(name), input_exists(name), input_hash(name), artifact_hash(name)
# status
def derive_status(task, graph, project, store) -> TaskStatus
def status_board(graph, project, store) -> list[TaskStatus]
def full_fingerprint(task, project) -> str
# scheduler
class Scheduler: run_target(target, wait=False) -> RunReport; cancel(run_id)
# ffmpeg
def run_ffmpeg(args, *, total_s=None, on_progress=None, cancel=None, ffmpeg_cmd=("ffmpeg",)) -> FfmpegResult
def filter_path(p) -> str
```

---

### Task 1: Package skeleton, Python pin and test harness

**Files:**
- Create: `mise.toml`, `.gitignore`, `engine/pyproject.toml`, `engine/lychnia/__init__.py`, `engine/tests/__init__.py`, `engine/tests/conftest.py`, `engine/tests/unit/__init__.py`, `engine/tests/unit/test_package.py`, `engine/tests/golden/__init__.py`

**Interfaces:**
- Produces: importable package `lychnia` with `__version__`; pytest fixture `fixture_dir` (Path to `tests/golden/fixtures/2026-08-30`).

- [ ] **Step 1: Pin Python for the repo and create the venv**

Run from the repo root:

```bash
mise use python@3.12.14
python --version            # expected: Python 3.12.14
cd engine 2>/dev/null || mkdir -p engine && cd engine
python -m venv .venv
```

`mise use` writes `mise.toml` at the repo root:

```toml
[tools]
python = "3.12.14"
```

- [ ] **Step 2: Check `.gitignore` at the repo root**

It already exists (created with the Claude Code hooks on 2026-09-04). Make sure it contains these entries and add any that are missing:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
engine/.venv/

# Engine runtime files
*.partial
```

Note: `engine/tests/unit/test_roadmap_consistency.py` already exists too (it checks `docs/ROADMAP.md` against the specs and plans). It starts running with the suite from this task on; keep it green.

- [ ] **Step 3: Write `engine/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "lychnia"
version = "0.1.0"
description = "Lychnia Engine: orchestrator, local API and CLI for the sermon pipeline"
readme = "../README.md"
requires-python = ">=3.12,<3.13"
dependencies = [
  "pydantic>=2.7,<3",
  "tomlkit>=0.13,<1",
  "platformdirs>=4.2,<5",
]

[project.optional-dependencies]
dev = ["pytest>=8.2,<9"]

[tool.hatch.build.targets.wheel]
packages = ["lychnia"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["media: needs real media files (opt-in smoke tests)"]
addopts = "-m 'not media'"
```

- [ ] **Step 4: Write the package init and the test harness**

`engine/lychnia/__init__.py`:

```python
"""Lychnia Engine: the Python process that runs the sermon pipeline."""

__version__ = "0.1.0"
```

`engine/tests/__init__.py`, `engine/tests/unit/__init__.py`, `engine/tests/golden/__init__.py`: empty files.

`engine/tests/conftest.py`:

```python
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "golden" / "fixtures" / "2026-08-30"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURES
```

`engine/tests/unit/test_package.py`:

```python
import lychnia


def test_version_is_set():
    assert lychnia.__version__ == "0.1.0"
```

- [ ] **Step 5: Install and run the test**

Follow the `dependency-hygiene` skill for this step (it runs osv-scanner over the resolved set).

```bash
cd engine && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest -v
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add mise.toml .gitignore engine/pyproject.toml engine/lychnia/__init__.py engine/tests
git commit -m "feat(engine): package skeleton, Python 3.12 pin and pytest harness"
```

---

### Task 2: Errors and i18n

**Files:**
- Create: `engine/lychnia/errors.py`, `engine/lychnia/i18n/__init__.py`, `engine/lychnia/i18n/es.toml`, `engine/lychnia/i18n/en.toml`
- Test: `engine/tests/unit/test_i18n.py`, `engine/tests/unit/test_errors.py`

**Interfaces:**
- Produces: `LychniaError(key, **params)`, `ConfigError(field, key, **params)`, `TaskError(key, *, command=None, stderr_tail="", **params)`, `Cancelled()`; `t(key, lang=None, **params) -> str`, `load_messages(lang) -> dict[str, str]`, `flatten(table, prefix="") -> dict[str, str]`, `available_languages() -> list[str]`, `current_language() -> str`, `DEFAULT_LANG = "es"`. Language from `LYCHNIA_LANG` env var when `lang` is None.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_i18n.py`:

```python
import pytest

from lychnia import i18n


def test_es_and_en_have_the_same_keys():
    es = i18n.load_messages("es")
    en = i18n.load_messages("en")
    assert set(es) == set(en)
    assert es  # not empty


def test_default_language_is_spanish(monkeypatch):
    monkeypatch.delenv("LYCHNIA_LANG", raising=False)
    assert i18n.current_language() == "es"


def test_env_var_selects_language(monkeypatch):
    monkeypatch.setenv("LYCHNIA_LANG", "en")
    assert i18n.current_language() == "en"
    assert i18n.t("validation.cut_end_before_start") == i18n.load_messages("en")["validation.cut_end_before_start"]


def test_t_formats_params():
    msg = i18n.t("validation.missing_field", lang="en", field="cut.end")
    assert "cut.end" in msg


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        i18n.t("nope.missing", lang="es")


def test_flatten_nests_with_dots():
    assert i18n.flatten({"a": {"b": "x"}, "c": "y"}) == {"a.b": "x", "c": "y"}


def test_available_languages():
    assert i18n.available_languages() == ["en", "es"]
```

`engine/tests/unit/test_errors.py`:

```python
from lychnia.errors import Cancelled, ConfigError, LychniaError, TaskError


def test_config_error_carries_field_and_key():
    err = ConfigError("cut.end", "validation.cut_end_before_start")
    assert err.field == "cut.end"
    assert err.key == "validation.cut_end_before_start"
    assert err.params["field"] == "cut.end"
    assert isinstance(err, LychniaError)


def test_task_error_keeps_command_and_stderr():
    err = TaskError("task.ffmpeg_failed", command=["ffmpeg", "-i", "x"], stderr_tail="boom", code=1)
    assert err.command == ["ffmpeg", "-i", "x"]
    assert err.stderr_tail == "boom"
    assert err.params == {"code": 1}


def test_cancelled_has_key():
    assert Cancelled().key == "task.cancelled"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_i18n.py tests/unit/test_errors.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lychnia.i18n'`.

- [ ] **Step 3: Write `engine/lychnia/errors.py`**

```python
"""Exceptions that carry an operator-facing i18n message key.

The exception text itself stays English (developer-facing); the operator sees
`lychnia.i18n.t(err.key, **err.params)`.
"""
from __future__ import annotations


class LychniaError(Exception):
    """Base error. `key` is an i18n key; `params` fill its placeholders."""

    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(f"{key} {params}" if params else key)


class ConfigError(LychniaError):
    """A project.toml field is missing or invalid. `field` is the dotted TOML path."""

    def __init__(self, field: str, key: str, **params: object) -> None:
        self.field = field
        super().__init__(key, field=field, **params)


class TaskError(LychniaError):
    """A task cannot start or failed. Keeps the failing command and its stderr tail."""

    def __init__(self, key: str, *, command: list[str] | None = None,
                 stderr_tail: str = "", **params: object) -> None:
        self.command = command
        self.stderr_tail = stderr_tail
        super().__init__(key, **params)


class Cancelled(LychniaError):
    """The operator cancelled the run."""

    def __init__(self) -> None:
        super().__init__("task.cancelled")
```

- [ ] **Step 4: Write `engine/lychnia/i18n/__init__.py`**

```python
"""Operator-facing strings. Keys are English snake_case, dotted by section.

Spanish (`es`) is the default and ships with the Engine; English (`en`) ships too.
Developer logs and exception internals stay in English and never come through here.
"""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from importlib import resources

DEFAULT_LANG = "es"


def flatten(table: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in table.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, full))
        else:
            out[full] = str(value)
    return out


def available_languages() -> list[str]:
    files = resources.files(__package__)
    return sorted(p.name.removesuffix(".toml") for p in files.iterdir() if p.name.endswith(".toml"))


@lru_cache(maxsize=None)
def load_messages(lang: str) -> dict[str, str]:
    text = resources.files(__package__).joinpath(f"{lang}.toml").read_text(encoding="utf-8")
    return flatten(tomllib.loads(text))


def current_language() -> str:
    return os.environ.get("LYCHNIA_LANG", DEFAULT_LANG)


def t(key: str, lang: str | None = None, **params: object) -> str:
    """Translate `key`. Unknown keys raise KeyError so tests catch them early."""
    messages = load_messages(lang or current_language())
    if key not in messages:
        raise KeyError(f"i18n key not found: {key}")
    return messages[key].format(**params)
```

- [ ] **Step 5: Write `engine/lychnia/i18n/es.toml`**

```toml
# Textos para el operador. Voseo suave, como el Makefile original.

[validation]
missing_field = "Falta el campo {field} en project.toml."
unknown_field = "El campo {field} no existe en project.toml; revisá el nombre."
invalid_value = "El valor de {field} no es válido: {value!r}."
cut_missing = "Falta [cut] (start y end, en segundos del maestro): es la decisión del Gate A."
cut_end_before_start = "cut.end debe ser mayor que cut.start."
audio_delay_negative = "sync.audio_delay_ms debe ser >= 0; para adelantar el audio, corregí los offsets de las cámaras."
master_limit_before_cut = "MASTER_LIMIT={limit} cae antes de cut.start ({start})."
short_end_before_start = "El short {id} termina antes de empezar (start >= end)."
phases_gap = "Las fases del plan tienen un hueco o solape entre {end} y {start}."
phases_start_mismatch = "La primera fase arranca en {phase} pero cut.start es {cut}."
phases_end_mismatch = "La última fase termina en {phase} pero cut.end es {cut}."
config_unreadable = "No se pudo leer project.toml: {detail}"

[status]
missing_input = "falta: {items}"
blocked = "esperando aprobación de: {items}"
ready = "listo para correr"
queued = "en cola"
running = "corriendo"
done = "hecho"
stale = "desactualizado: cambió una entrada o la configuración"
failed = "falló: {error}"
awaiting_approval = "hecho; falta aprobarlo"
approval_expired = "aprobado, pero algo cambió después: revisalo y volvé a aprobarlo"
unregistered = "existe en disco pero no está registrado; corré la tarea para registrarlo"
cancelled = "cancelado"

[action]
run_task = "corré: lychnia run {task}"
approve = "aprobalo: lychnia approve {artifact}"
provide = "aportalo: lychnia provide {artifact} <archivo>"
fill_config = "completá {section} en project.toml"
add_source = "poné el archivo en input/ y completá sources.{source} en project.toml"

[task]
cancelled = "cancelado por el operador"
ffmpeg_failed = "ffmpeg falló (código {code}); mirá el log de la corrida"
ffmpeg_missing = "no se encuentra ffmpeg; instalalo o indicá su ruta en la configuración del Engine"
output_missing = "la tarea terminó sin producir {artifact}"

[template]
header = "project.toml: la ÚNICA fuente de verdad de esta prédica. Lo que se deriva (duración, frames, fin de cada cámara) NO se escribe aquí."
meta = "se escribe UNA vez; miniatura, blog y metadata lo leen"
meta_date = "AAAA-MM-DD (tomado del nombre de la carpeta)"
meta_slug = "kebab-case (idem)"
meta_title = "título de la prédica (blog/web)"
meta_passage = "p. ej. \"Génesis 8\""
meta_preacher = "nombre completo, bien escrito"
meta_author_id = "seniorPastor | associatePastor | guestSpeaker"
sources = "rutas relativas a esta carpeta; Lychnia las descubre en input/"
sources_master = "input/audio/<archivo> (el audio bueno; su video es el programa de OBS)"
sources_cam_a = "input/cam-wide/<archivo>"
sources_cam_b = "input/cam-preacher/<archivo>  (vacío si no hubo cámara del predicador)"
sync = "t_camera = t_master + offset"
sync_delay = "retrasar el audio N ms; >= 0"
cut = "decisión del Gate A, en segundos del MAESTRO (descomentá y completá)"
cut_start = "dónde arranca el video final"
cut_end = "dónde termina"
video = "filtros por cámara de la Fase 1 (opcional; estos son los default)"
audio = "las tres perillas de la cadena de voz (la cadena vive en el código)"
audio_downmix = "dual-mono | left | right  (medí L−R antes de decidir)"
audio_lufs = "objetivo de loudnorm (−16 limpio > −14 distorsionado)"
gate_b = "clip de muestra: un tramo con cambio de cámara + callouts"
shorts = "shorts 9:16; start/end imantados a silencios reales; el end remata en la frase fuerte"
shorts_overrides = "texto de una cue forzado a mano, por posición (\"-1\" = última, \"0\" = primera)"
plan = "plan de cámaras (Gate A): fases con la cámara del plano largo, su duración y la del descanso"
plan_closing_a = "últimos segundos en panorámica"
thumbnail = "textos de la miniatura; no repite el título del video"
publishing = "lo escribe el operador al publicar (subir queda fuera de v1)"
```

- [ ] **Step 6: Write `engine/lychnia/i18n/en.toml`**

```toml
# Operator-facing text, English.

[validation]
missing_field = "Field {field} is missing in project.toml."
unknown_field = "Field {field} does not exist in project.toml; check the name."
invalid_value = "The value of {field} is not valid: {value!r}."
cut_missing = "[cut] is missing (start and end, in master seconds): it is the Gate A decision."
cut_end_before_start = "cut.end must be greater than cut.start."
audio_delay_negative = "sync.audio_delay_ms must be >= 0; to advance the audio, correct the camera offsets."
master_limit_before_cut = "MASTER_LIMIT={limit} falls before cut.start ({start})."
short_end_before_start = "Short {id} ends before it starts (start >= end)."
phases_gap = "The plan phases have a gap or overlap between {end} and {start}."
phases_start_mismatch = "The first phase starts at {phase} but cut.start is {cut}."
phases_end_mismatch = "The last phase ends at {phase} but cut.end is {cut}."
config_unreadable = "project.toml could not be read: {detail}"

[status]
missing_input = "missing: {items}"
blocked = "waiting for approval of: {items}"
ready = "ready to run"
queued = "queued"
running = "running"
done = "done"
stale = "stale: an input or the configuration changed"
failed = "failed: {error}"
awaiting_approval = "done; approval pending"
approval_expired = "approved, but something changed afterwards: review it and approve again"
unregistered = "exists on disk but is not registered; run the task to register it"
cancelled = "cancelled"

[action]
run_task = "run: lychnia run {task}"
approve = "approve it: lychnia approve {artifact}"
provide = "provide it: lychnia provide {artifact} <file>"
fill_config = "fill in {section} in project.toml"
add_source = "put the file under input/ and fill in sources.{source} in project.toml"

[task]
cancelled = "cancelled by the operator"
ffmpeg_failed = "ffmpeg failed (exit code {code}); see the run log"
ffmpeg_missing = "ffmpeg was not found; install it or set its path in the Engine configuration"
output_missing = "the task finished without producing {artifact}"

[template]
header = "project.toml: the ONLY source of truth for this sermon. Derived values (duration, frames, camera end) are NOT written here."
meta = "written ONCE; thumbnail, blog and metadata read it"
meta_date = "YYYY-MM-DD (taken from the folder name)"
meta_slug = "kebab-case (idem)"
meta_title = "sermon title (blog/web)"
meta_passage = "e.g. \"Genesis 8\""
meta_preacher = "full name, spelled correctly"
meta_author_id = "seniorPastor | associatePastor | guestSpeaker"
sources = "paths relative to this folder; Lychnia discovers them under input/"
sources_master = "input/audio/<file> (the good audio; its video is the OBS program)"
sources_cam_a = "input/cam-wide/<file>"
sources_cam_b = "input/cam-preacher/<file>  (empty if there was no preacher camera)"
sync = "t_camera = t_master + offset"
sync_delay = "delay the audio N ms; >= 0"
cut = "Gate A decision, in MASTER seconds (uncomment and fill in)"
cut_start = "where the final video starts"
cut_end = "where it ends"
video = "per-camera filters for Phase 1 (optional; these are the defaults)"
audio = "the three knobs of the voice chain (the chain lives in code)"
audio_downmix = "dual-mono | left | right  (measure L−R before deciding)"
audio_lufs = "loudnorm target (−16 clean > −14 distorted)"
gate_b = "preview clip: a stretch with a camera change and callouts"
shorts = "9:16 shorts; start/end snapped to real silences; end lands on the strong quote"
shorts_overrides = "cue text forced by hand, by position (\"-1\" = last, \"0\" = first)"
plan = "camera plan (Gate A): phases with the long-shot camera, its duration and the rest-shot duration"
plan_closing_a = "last seconds on the wide shot"
thumbnail = "thumbnail texts; never repeats the video title"
publishing = "written by the operator when publishing (uploading is out of v1)"
```

- [ ] **Step 7: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_i18n.py tests/unit/test_errors.py -v`
Expected: all PASS (10 tests).

- [ ] **Step 8: Commit**

```bash
git add engine/lychnia/errors.py engine/lychnia/i18n engine/tests/unit/test_i18n.py engine/tests/unit/test_errors.py
git commit -m "feat(engine): error types with i18n keys; es/en message catalogs"
```

---

### Task 3: Frame grid and voice chain

**Files:**
- Create: `engine/lychnia/media/__init__.py` (empty), `engine/lychnia/media/grid.py`, `engine/lychnia/media/voice_chain.py`
- Test: `engine/tests/unit/test_grid.py`, `engine/tests/unit/test_voice_chain.py`

**Interfaces:**
- Produces: `FPS = 30`, `f30(t: float) -> float`, `on_grid(t: float, tol: float = 1e-4) -> bool`, `frames_for(duration: float) -> int`; `DOWNMIX: dict[str, str]` with keys `dual-mono`, `left`, `right`; `voice_filter(downmix: str, lufs: float, delay_ms: int = 0) -> str`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_grid.py`:

```python
from lychnia.media.grid import FPS, f30, frames_for, on_grid


def test_fps_is_30():
    assert FPS == 30


def test_f30_snaps_to_the_frame_grid():
    assert f30(632.8) == 632.8
    assert f30(649.2666) == 649.266667
    assert f30(700) == 700.0


def test_on_grid():
    assert on_grid(649.266667)
    assert not on_grid(649.27)


def test_frames_for_full_sermon_and_limited_run():
    assert frames_for(4685.0) == 140550
    assert frames_for(142.5) == 4275
```

`engine/tests/unit/test_voice_chain.py`:

```python
import pytest

from lychnia.media.voice_chain import DOWNMIX, voice_filter

ORIGINAL_AF_VOZ = ("pan=mono|c0=0.5*c0+0.5*c1,highpass=f=80,speechnorm=e=12.5:r=0.0008:l=1,"
                   "alimiter=limit=0.85,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=192000,"
                   "alimiter=limit=0.95,aresample=48000")


def test_default_chain_matches_the_original_cfg_af_voz():
    assert voice_filter("dual-mono", -15) == ORIGINAL_AF_VOZ


def test_chain_always_ends_with_48k_resample():
    for downmix in DOWNMIX:
        assert voice_filter(downmix, -16, 20).endswith("aresample=48000")


def test_delay_goes_right_after_the_downmix():
    af = voice_filter("left", -15, 20)
    assert af.startswith("pan=mono|c0=c0,adelay=20:all=1,highpass=f=80,")


def test_unknown_downmix_raises():
    with pytest.raises(KeyError):
        voice_filter("stereo", -15)
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_grid.py tests/unit/test_voice_chain.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/media/grid.py`**

```python
"""The 1/30 s frame grid (hard rule 2).

Segments are cut by exact frame count (`-frames:v round(dur*30)`), so every shot
boundary must sit on a multiple of 1/30 s or the residue accumulates as drift.
"""
from __future__ import annotations

FPS = 30


def f30(t: float) -> float:
    """Snap a time in seconds to the frame grid."""
    return round(round(t * FPS) / FPS, 6)


def on_grid(t: float, tol: float = 1e-4) -> bool:
    return abs(round(t * FPS) - t * FPS) < tol


def frames_for(duration: float) -> int:
    return int(round(duration * FPS))
```

- [ ] **Step 4: Write `engine/lychnia/media/voice_chain.py`**

```python
"""The canonical voice chain (hard rule 7). Lives once, here.

Per sermon only three knobs change: the downmix to mono, an optional delay and
the loudness target. The final `aresample=48000` is not optional: loudnorm
resamples to 192 kHz internally and the AAC track would end up at 96 kHz.
"""
from __future__ import annotations

DOWNMIX: dict[str, str] = {
    "dual-mono": "pan=mono|c0=0.5*c0+0.5*c1",   # both channels equal: average them
    "left": "pan=mono|c0=c0",                   # voice only on L
    "right": "pan=mono|c0=c1",
}

_CHAIN = ("highpass=f=80,"
          "speechnorm=e=12.5:r=0.0008:l=1,"
          "alimiter=limit=0.85,"
          "loudnorm=I={lufs}:TP=-1.5:LRA=11,"
          "aresample=192000,"           # 4x oversampling to see the true peak
          "alimiter=limit=0.95,"        # limits the real inter-sample peak
          "aresample=48000")            # delivery sample rate


def voice_filter(downmix: str, lufs: float, delay_ms: int = 0) -> str:
    """Full `-af` value: downmix, optional delay, canonical chain."""
    parts = [DOWNMIX[downmix]]
    if delay_ms:
        parts.append(f"adelay={delay_ms}:all=1")
    parts.append(_CHAIN.format(lufs=f"{lufs:g}"))
    return ",".join(parts)
```

- [ ] **Step 5: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_grid.py tests/unit/test_voice_chain.py -v`
Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/lychnia/media engine/tests/unit/test_grid.py engine/tests/unit/test_voice_chain.py
git commit -m "feat(engine): frame grid helpers and canonical voice chain"
```

---

### Task 4: Project configuration model

**Files:**
- Create: `engine/lychnia/project/__init__.py` (empty), `engine/lychnia/project/config.py`
- Test: `engine/tests/unit/test_config.py`

**Interfaces:**
- Consumes: `ConfigError` (Task 2), `f30`, `frames_for` (Task 3).
- Produces: pydantic models `Meta, Sources, Sync, Cut, Video, Audio, GateB, Short, Phase, Plan, Thumbnail, Publishing, ProjectConfig`; `VF_DEFAULT_A`, `VF_DEFAULT_B`; `parse_config(data: dict, master_limit: float | None = None) -> ProjectConfig`; `load_config(path: Path, master_limit: float | None = None) -> ProjectConfig`. `ProjectConfig` properties: `master_limit`, `require_cut() -> Cut`, `end`, `duration`, `frame_count`, `cut_fingerprint`, `video_fingerprint`, `audio_fingerprint`, `has_input(dotted: str) -> bool`, `gate_b_window() -> tuple[float, float]`.
- Validation failures surface as `ConfigError(field, key, ...)`, never as pydantic exceptions.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_config.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lychnia.project'`.

- [ ] **Step 3: Write `engine/lychnia/project/config.py`**

Fetch pydantic v2 docs (`library-docs` skill) for `model_validator`, `field_validator`, `ConfigDict(extra="forbid")` and `ValidationError.errors()` before writing.

```python
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
        """Cut end, bounded by MASTER_LIMIT and snapped to the frame grid."""
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
```

Note on `_convert`: a `model_validator` on `Cut` reports `loc == ("cut",)`, so `field == "cut"`; a `field_validator` on `Sync.audio_delay_ms` reports `("sync", "audio_delay_ms")`. Params travel inside the `ValueError` message separated by `|` because pydantic only keeps the message string; `_convert` splits them back.

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_config.py -v`
Expected: 14 PASS. If `test_unknown_field_and_bad_downmix` reports `field == "audio.mezcla"` correctly but `test_short_end_before_start` shows `field == "shorts.0"`, that is acceptable: the test only checks key and `id` param.

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/project engine/tests/unit/test_config.py
git commit -m "feat(engine): project.toml model with derived values and fingerprints"
```

---

### Task 5: Legacy adapter and golden config test

**Files:**
- Create: `engine/tests/golden/legacy.py`, `engine/tests/golden/test_config_golden.py`

**Interfaces:**
- Consumes: `parse_config` (Task 4), fixture `fixture_dir` (Task 1).
- Produces: `legacy_to_config_dict(data: dict) -> dict`, `load_legacy_config(path: Path, master_limit: float | None = None) -> ProjectConfig`, `LEGACY_ARTIFACTS: dict[str, str]` mapping logical names to fixture file names (`transcript.srt` → `predica.srt`, `transcript.tsv` → `predica.tsv`, `callouts.toml` → `callouts.toml`, `silences.raw.txt` → `silencios.raw.txt`, `expected.camera_plan.json` → `esperado_plan_camaras.json`, `expected.callouts.ass` → `esperado_callouts.ass`, `expected.callouts_render.ass` → `esperado_callouts_render.ass`). Plan 02 golden tests import these.

- [ ] **Step 1: Write the failing golden test**

`engine/tests/golden/test_config_golden.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd engine && .venv/bin/pytest tests/golden -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.golden.legacy'`.

- [ ] **Step 3: Write `engine/tests/golden/legacy.py`**

```python
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
```

- [ ] **Step 4: Run the golden tests**

Run: `cd engine && .venv/bin/pytest tests/golden -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/tests/golden/legacy.py engine/tests/golden/test_config_golden.py
git commit -m "test(engine): legacy adapter and golden config test for the 2026-08-30 sermon"
```

---

### Task 6: Comment-preserving config edits

**Files:**
- Create: `engine/lychnia/project/config_edit.py`
- Test: `engine/tests/unit/test_config_edit.py`

**Interfaces:**
- Consumes: `parse_config`, `ProjectConfig` (Task 4), `ConfigError` (Task 2).
- Produces: `patch_config(path: Path, patch: dict[str, dict[str, object]], master_limit: float | None = None) -> ProjectConfig`. Validates the patched document before writing; writes atomically (`project.toml.partial` then `os.replace`); on validation failure the file is untouched. `read_raw(path) -> str`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_config_edit.py`:

```python
import pytest

from lychnia.errors import ConfigError
from lychnia.project.config_edit import patch_config, read_raw

ORIGINAL = """# header comment
[meta]                              # written once
date = "2026-09-06"                 # YYYY-MM-DD
slug = "prueba"

[sources]
master = "input/audio/m.mkv"        # the good audio

[cut]                               # Gate A decision
start = 100.0                       # where it starts
end   = 200.0
"""


def _write(tmp_path):
    p = tmp_path / "project.toml"
    p.write_text(ORIGINAL, encoding="utf-8")
    return p


def test_patch_changes_value_and_keeps_comments(tmp_path):
    p = _write(tmp_path)
    cfg = patch_config(p, {"cut": {"start": 120.5}})
    assert cfg.cut.start == 120.5
    text = read_raw(p)
    assert "# header comment" in text
    assert "# where it starts" in text
    assert "# Gate A decision" in text
    assert "start = 120.5" in text
    assert 'master = "input/audio/m.mkv"        # the good audio' in text


def test_patch_adds_missing_section_and_key(tmp_path):
    p = _write(tmp_path)
    cfg = patch_config(p, {"audio": {"downmix": "left"}, "meta": {"title": "T"}})
    assert cfg.audio.downmix == "left"
    assert cfg.meta.title == "T"
    assert "[audio]" in read_raw(p)


def test_invalid_patch_leaves_the_file_untouched(tmp_path):
    p = _write(tmp_path)
    with pytest.raises(ConfigError) as exc:
        patch_config(p, {"cut": {"end": 50.0}})
    assert exc.value.key == "validation.cut_end_before_start"
    assert read_raw(p) == ORIGINAL
    assert not (tmp_path / "project.toml.partial").exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_config_edit.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/project/config_edit.py`**

Fetch tomlkit docs (`library-docs` skill) for `parse`, `dumps`, `table()` and item assignment. tomlkit keeps the trailing comment of a key when its value is replaced by assignment; the first test pins that behaviour.

```python
"""Edit `project.toml` by sections, preserving the operator's comments (tomlkit)."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomlkit

from lychnia.project.config import ProjectConfig, parse_config


def read_raw(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def patch_config(path: Path, patch: dict[str, dict[str, object]],
                 master_limit: float | None = None) -> ProjectConfig:
    """Apply `{section: {field: value}}`, validate, then write atomically."""
    path = Path(path)
    doc = tomlkit.parse(read_raw(path))
    for section, fields in patch.items():
        if section not in doc:
            doc.add(section, tomlkit.table())
        for key, value in fields.items():
            doc[section][key] = value
    text = tomlkit.dumps(doc)
    cfg = parse_config(tomllib.loads(text), master_limit)   # raises ConfigError, file untouched
    partial = path.with_name(path.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)
    return cfg
```

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_config_edit.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/project/config_edit.py engine/tests/unit/test_config_edit.py
git commit -m "feat(engine): patch project.toml by sections without losing comments"
```

---

### Task 7: File hashing

**Files:**
- Create: `engine/lychnia/orchestrator/__init__.py` (empty), `engine/lychnia/orchestrator/hashing.py`
- Test: `engine/tests/unit/test_hashing.py`

**Interfaces:**
- Produces: `LARGE_THRESHOLD = 64 * 2**20`, `EDGE_BYTES = 8 * 2**20`, `hash_file(path: Path, large_threshold: int = LARGE_THRESHOLD) -> str` (`sha256:<hex>` or `large:<hex>`), `hash_text(text: str) -> str` (`sha256:<hex>` of UTF-8 bytes).

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_hashing.py`:

```python
import hashlib
import os

from lychnia.orchestrator.hashing import hash_file, hash_text


def test_small_file_is_full_sha256(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"hello")
    assert hash_file(p) == "sha256:" + hashlib.sha256(b"hello").hexdigest()
    assert hash_text("hello") == hash_file(p)


def test_large_mode_uses_size_mtime_and_edges(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(os.urandom(4096))
    h1 = hash_file(p, large_threshold=1024)
    assert h1.startswith("large:")
    assert hash_file(p, large_threshold=1024) == h1
    # a change in the middle of a huge file is invisible by design; a change at the edge is not
    data = bytearray(p.read_bytes())
    data[0] ^= 0xFF
    p.write_bytes(bytes(data))
    assert hash_file(p, large_threshold=1024) != h1


def test_large_mode_changes_with_size(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(b"x" * 3000)
    h1 = hash_file(p, large_threshold=1024)
    p.write_bytes(b"x" * 3001)
    assert hash_file(p, large_threshold=1024) != h1
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_hashing.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/orchestrator/hashing.py`**

```python
"""Content hashes for the artifact registry (spec §6.1).

Small files (TOML, SRT, JSON, ASS): full SHA-256. Large media files: size, mtime and
the SHA-256 of the first and last 8 MiB, so a 5 GB master hashes in milliseconds.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

LARGE_THRESHOLD = 64 * 2**20
EDGE_BYTES = 8 * 2**20


def hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: Path, large_threshold: int = LARGE_THRESHOLD) -> str:
    path = Path(path)
    stat = path.stat()
    digest = hashlib.sha256()
    if stat.st_size <= large_threshold:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    digest.update(f"{stat.st_size}|{stat.st_mtime_ns}|".encode())
    with path.open("rb") as fh:
        digest.update(fh.read(EDGE_BYTES))
        fh.seek(max(stat.st_size - EDGE_BYTES, 0))
        digest.update(fh.read(EDGE_BYTES))
    return "large:" + digest.hexdigest()
```

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_hashing.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/orchestrator engine/tests/unit/test_hashing.py
git commit -m "feat(engine): content hashes with a fast path for large media"
```

---

### Task 8: Project layout, source discovery and the project.toml template

**Files:**
- Create: `engine/lychnia/project/layout.py`, `engine/lychnia/project/discovery.py`, `engine/lychnia/project/template.py`, `engine/lychnia/resources/__init__.py` (empty), `engine/lychnia/resources/INFO.es.md`, `engine/lychnia/resources/INFO.en.md`
- Test: `engine/tests/unit/test_layout.py`, `engine/tests/unit/test_template.py`

**Interfaces:**
- Consumes: `t` (Task 2), `load_config` (Task 4).
- Produces: `ProjectPaths(root)` with `config_file`, `input`, `audio`, `cam_wide`, `cam_preacher`, `photos`, `info_md`, `transcript`, `outline`, `video`, `video_work`, `gate_a`, `gate_b`, `shorts`, `youtube`, `youtube_assets`, `blog`, `blog_images`, `state_dir`, `state_db`, `logs`, `all_dirs() -> list[Path]`, `ensure() -> None`; `MEDIA_SUFFIXES`, `discover_sources(paths: ProjectPaths) -> dict[str, str]` (keys `master`, `cam_a`, `cam_b`; values relative POSIX paths or `""`); `render_project_toml(date: str, slug: str, sources: dict[str, str], lang: str | None = None) -> str`; `create_project(root: Path, date: str, slug: str, lang: str | None = None) -> Path` (returns the project folder `root / f"{date}_{slug}"`; never overwrites a `project.toml` that already has a master source; `adopt_project(folder: Path, lang=None) -> Path` for an existing folder).

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_layout.py`:

```python
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
```

`engine/tests/unit/test_template.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_layout.py tests/unit/test_template.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/project/layout.py`**

```python
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
```

- [ ] **Step 4: Write `engine/lychnia/project/discovery.py`**

```python
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
```

- [ ] **Step 5: Write `engine/lychnia/project/template.py`**

```python
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
                 "end     = 3055.30", 'keyword = "palabra"', 'title   = "Titulo gancho"', "",
                 t("template.shorts_overrides", lang), '[shorts_overrides."s1-slug"]',
                 '"-1" = "texto forzado de la ultima cue"']:
        doc.add(tomlkit.comment(line) if line else tomlkit.nl())

    plan = _table("template.plan", lang, closing_a=26.0)
    _annotate(plan, lang, closing_a="template.plan_closing_a")
    for line in ["[[plan.phases]]", "start     = 557.5", "end       = 570.0", 'cam       = "A"',
                 "long_shot = 12.5", "rest_shot = 0.0", 'note      = "establishing shot"']:
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
```

- [ ] **Step 6: Write the INFO.md templates**

`engine/lychnia/resources/INFO.es.md` (operator-facing, Spanish; exception 3 of the language policy):

```markdown
# INFO de la prédica

> Lo llena el operador antes de procesar. Son los datos que no se deducen del audio ni del video.
> Dejá los archivos en `input/` (`audio/`, `cam-wide/`, `cam-preacher/`, `photos/`).

## Datos de la prédica

- **Fecha (AAAA-MM-DD):**
- **Título tentativo:**
- **Predicador:** _(nombre completo, bien escrito)_
- **Rol del predicador:** `seniorPastor` | `associatePastor` | `guestSpeaker`
- **Serie / tema (si aplica):**
- **Pasaje(s) base:** _(p. ej. Josué 1:1-9)_
- **Versión de la Biblia:** _(por defecto: Reina-Valera 1960)_

## Indicaciones

- **Anuncios / notas a incluir (opcional):**
- **Momentos especiales (testimonio, bautizo, llamado al altar) con minuto aproximado:**
- **Frases que el predicador quiere destacar (opcional):**

## Checklist

- [ ] `input/audio/`: grabación maestra de OBS (el audio bueno).
- [ ] `input/cam-wide/`: Cámara A (plano abierto), completa.
- [ ] `input/cam-preacher/`: Cámara B (sigue al predicador), completa. Puede faltar.
- [ ] `input/photos/`: fotos del día.
- [ ] Este `INFO.md` lleno.
```

`engine/lychnia/resources/INFO.en.md`: same structure in English (translate every line; keep the field list identical).

- [ ] **Step 7: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_layout.py tests/unit/test_template.py -v`
Expected: 6 PASS. If tomlkit renders `[cut]` with only comments differently than expected, `tomllib.loads` must still return `{}` for it; that is what the first template test allows.

- [ ] **Step 8: Commit**

```bash
git add engine/lychnia/project/layout.py engine/lychnia/project/discovery.py engine/lychnia/project/template.py engine/lychnia/resources engine/tests/unit/test_layout.py engine/tests/unit/test_template.py
git commit -m "feat(engine): project layout, source discovery and localized project.toml template"
```

---

### Task 9: SQLite state store

**Files:**
- Create: `engine/lychnia/orchestrator/state.py`
- Test: `engine/tests/unit/test_state.py`

**Interfaces:**
- Produces: `ArtifactRecord(name, path, hash, fingerprint, producer, produced_at, approved_hash, approved_by, approved_at, edited)`, `RunRecord(id, task, started_at, finished_at, status, error, master_limit, log_path)`, `StateStore(path: Path)` with `record_artifact(name, path, hash, fingerprint, producer) -> None`, `get_artifact(name) -> ArtifactRecord | None`, `list_artifacts() -> list[ArtifactRecord]`, `approve(name, hash, who) -> None`, `revoke_approval(name) -> None`, `mark_edited(name, hash) -> None`, `start_run(task, master_limit=None, log_path=None) -> int`, `set_run_status(run_id, status) -> None`, `finish_run(run_id, status, error=None) -> None`, `latest_run(task) -> RunRecord | None`, `get_run(run_id) -> RunRecord | None`, `add_event(run_id, type, payload: dict) -> None`, `events_for(run_id) -> list[tuple[str, str, dict]]`, `close()`. Run statuses: `queued`, `running`, `done`, `failed`, `cancelled`. Thread-safe (one connection, one lock).

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_state.py`:

```python
import sqlite3

from lychnia.orchestrator.state import StateStore


def test_artifact_roundtrip_and_approval(tmp_path):
    store = StateStore(tmp_path / ".lychnia" / "state.sqlite")
    assert store.get_artifact("camera_plan.json") is None
    store.record_artifact("camera_plan.json", "outline/camera_plan.json", "sha256:aa", "fp1", "plan")
    rec = store.get_artifact("camera_plan.json")
    assert (rec.hash, rec.fingerprint, rec.producer, rec.approved_hash, rec.edited) == ("sha256:aa", "fp1", "plan", None, False)
    store.approve("camera_plan.json", "sha256:aa", "andres")
    rec = store.get_artifact("camera_plan.json")
    assert rec.approved_hash == "sha256:aa" and rec.approved_by == "andres" and rec.approved_at
    store.mark_edited("camera_plan.json", "sha256:bb")
    rec = store.get_artifact("camera_plan.json")
    assert rec.edited is True and rec.hash == "sha256:bb" and rec.approved_hash == "sha256:aa"
    store.revoke_approval("camera_plan.json")
    assert store.get_artifact("camera_plan.json").approved_hash is None
    assert [a.name for a in store.list_artifacts()] == ["camera_plan.json"]


def test_recording_again_replaces_but_keeps_approval(tmp_path):
    store = StateStore(tmp_path / "s.sqlite")
    store.record_artifact("x", "x", "h1", "f1", "t")
    store.approve("x", "h1", "a")
    store.record_artifact("x", "x", "h2", "f2", "t")
    rec = store.get_artifact("x")
    assert (rec.hash, rec.fingerprint, rec.approved_hash, rec.edited) == ("h2", "f2", "h1", False)


def test_runs_and_events(tmp_path):
    store = StateStore(tmp_path / "s.sqlite")
    assert store.latest_run("render") is None
    r1 = store.start_run("render", master_limit=700, log_path=".lychnia/logs/1.log")
    run = store.latest_run("render")
    assert run.id == r1 and run.status == "queued" and run.master_limit == 700 and run.finished_at is None
    store.set_run_status(r1, "running")
    assert store.get_run(r1).status == "running"
    store.add_event(r1, "task.progress", {"pct": 50})
    store.finish_run(r1, "failed", error="boom")
    run = store.get_run(r1)
    assert run.status == "failed" and run.error == "boom" and run.finished_at
    r2 = store.start_run("render")
    assert store.latest_run("render").id == r2
    assert store.events_for(r1) == [("task.progress", store.events_for(r1)[0][1], {"pct": 50})]


def test_store_can_be_deleted_and_recreated(tmp_path):
    p = tmp_path / "s.sqlite"
    store = StateStore(p)
    store.record_artifact("x", "x", "h", "f", "t")
    store.close()
    p.unlink()
    store2 = StateStore(p)
    assert store2.get_artifact("x") is None
    assert sqlite3.connect(p).execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/orchestrator/state.py`**

```python
"""Per-project registry in SQLite (spec §6.2): artifacts, runs, events.

The store can be deleted without losing work: statuses are derived from disk and the
Engine reports outputs without a row as `unregistered` until their task runs again.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (
  name TEXT PRIMARY KEY, path TEXT NOT NULL, hash TEXT, fingerprint TEXT, producer TEXT,
  produced_at TEXT, approved_hash TEXT, approved_by TEXT, approved_at TEXT, edited INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
  status TEXT NOT NULL, error TEXT, master_limit REAL, log_path TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, t TEXT NOT NULL, type TEXT NOT NULL, payload TEXT);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class ArtifactRecord:
    name: str
    path: str
    hash: str | None
    fingerprint: str | None
    producer: str | None
    produced_at: str | None
    approved_hash: str | None
    approved_by: str | None
    approved_at: str | None
    edited: bool


@dataclass(frozen=True)
class RunRecord:
    id: int
    task: str
    started_at: str
    finished_at: str | None
    status: str
    error: str | None
    master_limit: float | None
    log_path: str | None


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _run(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._db.execute(sql, params)
            self._db.commit()
            return cur

    # ── artifacts ────────────────────────────────────────────────────────
    def record_artifact(self, name: str, path: str, hash: str, fingerprint: str, producer: str) -> None:
        self._run("""INSERT INTO artifacts(name, path, hash, fingerprint, producer, produced_at, edited)
                     VALUES (?, ?, ?, ?, ?, ?, 0)
                     ON CONFLICT(name) DO UPDATE SET path=excluded.path, hash=excluded.hash,
                       fingerprint=excluded.fingerprint, producer=excluded.producer,
                       produced_at=excluded.produced_at, edited=0""",
                  (name, path, hash, fingerprint, producer, _now()))

    def get_artifact(self, name: str) -> ArtifactRecord | None:
        row = self._run("SELECT * FROM artifacts WHERE name = ?", (name,)).fetchone()
        return self._artifact(row) if row else None

    def list_artifacts(self) -> list[ArtifactRecord]:
        return [self._artifact(r) for r in self._run("SELECT * FROM artifacts ORDER BY name").fetchall()]

    def approve(self, name: str, hash: str, who: str) -> None:
        self._run("UPDATE artifacts SET approved_hash=?, approved_by=?, approved_at=? WHERE name=?",
                  (hash, who, _now(), name))

    def revoke_approval(self, name: str) -> None:
        self._run("UPDATE artifacts SET approved_hash=NULL, approved_by=NULL, approved_at=NULL WHERE name=?", (name,))

    def mark_edited(self, name: str, hash: str) -> None:
        self._run("UPDATE artifacts SET hash=?, edited=1 WHERE name=?", (hash, name))

    @staticmethod
    def _artifact(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(row["name"], row["path"], row["hash"], row["fingerprint"], row["producer"],
                              row["produced_at"], row["approved_hash"], row["approved_by"], row["approved_at"],
                              bool(row["edited"]))

    # ── runs ─────────────────────────────────────────────────────────────
    def start_run(self, task: str, master_limit: float | None = None, log_path: str | None = None) -> int:
        cur = self._run("INSERT INTO runs(task, started_at, status, master_limit, log_path) VALUES (?, ?, 'queued', ?, ?)",
                        (task, _now(), master_limit, log_path))
        return int(cur.lastrowid)

    def set_run_status(self, run_id: int, status: str) -> None:
        self._run("UPDATE runs SET status=? WHERE id=?", (status, run_id))

    def finish_run(self, run_id: int, status: str, error: str | None = None) -> None:
        self._run("UPDATE runs SET status=?, error=?, finished_at=? WHERE id=?", (status, error, _now(), run_id))

    def get_run(self, run_id: int) -> RunRecord | None:
        row = self._run("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._runrec(row) if row else None

    def latest_run(self, task: str) -> RunRecord | None:
        row = self._run("SELECT * FROM runs WHERE task=? ORDER BY id DESC LIMIT 1", (task,)).fetchone()
        return self._runrec(row) if row else None

    @staticmethod
    def _runrec(row: sqlite3.Row) -> RunRecord:
        return RunRecord(row["id"], row["task"], row["started_at"], row["finished_at"], row["status"],
                         row["error"], row["master_limit"], row["log_path"])

    # ── events ───────────────────────────────────────────────────────────
    def add_event(self, run_id: int | None, type: str, payload: dict) -> None:
        self._run("INSERT INTO events(run_id, t, type, payload) VALUES (?, ?, ?, ?)",
                  (run_id, _now(), type, json.dumps(payload, ensure_ascii=False)))

    def events_for(self, run_id: int) -> list[tuple[str, str, dict]]:
        rows = self._run("SELECT type, t, payload FROM events WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        return [(r["type"], r["t"], json.loads(r["payload"])) for r in rows]
```

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_state.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/orchestrator/state.py engine/tests/unit/test_state.py
git commit -m "feat(engine): SQLite state store for artifacts, runs and events"
```

---

### Task 10: Artifacts, tasks, graph and the Project object

**Files:**
- Create: `engine/lychnia/orchestrator/artifacts.py`, `engine/lychnia/orchestrator/task.py`, `engine/lychnia/orchestrator/graph.py`, `engine/lychnia/project/project.py`
- Test: `engine/tests/unit/test_graph.py`, `engine/tests/unit/test_project.py`, `engine/tests/unit/fakes.py`
- Modify: `engine/tests/conftest.py` (add `make_project`)

**Interfaces:**
- Consumes: `hash_file` (Task 7), `StateStore` (Task 9), `load_config`, `ProjectConfig` (Task 4), `ProjectPaths` (Task 8).
- Produces:
  - `ArtifactSpec(name: str, path: str, providable: bool = False)`; `ARTIFACTS: dict[str, ArtifactSpec]` (the registry of spec §5 logical names); `SOURCE_PREFIX = "source:"`, `CONFIG_PREFIX = "config:"`, `is_source(name)`, `is_config(name)`.
  - `Resource` enum (`GPU="gpu"`, `CPU_HEAVY="cpu_heavy"`, `LIGHT="light"`), `Gate` enum (`NONE="none"`, `A="gate_a"`, `B="gate_b"`), abstract `Task` with class attributes `name: str`, `inputs: tuple[str, ...]`, `outputs: tuple[str, ...]`, `resource: Resource`, `gate: Gate`, `on_demand: bool = False`, methods `fingerprint(self, cfg: ProjectConfig) -> str` and `run(self, ctx) -> None`.
  - `TaskGraph(tasks: Iterable[Task])`: `tasks: dict[str, Task]`, `producer_of(name) -> Task | None`, `dependencies(task) -> list[Task]` (producers of its inputs, excluding `on_demand` ones), `closure(names: Iterable[str]) -> list[Task]` (topological order, dependencies first, `on_demand` tasks only when named explicitly), `resolve_target(target: str) -> list[Task]` (composite target or single task name; `KeyError` otherwise); `TARGETS: dict[str, tuple[str, ...]]` = `prepare=(transcribe, camera_health)`, `gate_a=(callouts, control_frames)`, `video=(segments, preview)`, `content=(subtitles, thumbnail, blog)`, `deliver=(render, shorts)`.
  - `Project(root: Path, master_limit: float | None = None, artifacts: dict[str, ArtifactSpec] | None = None)`: `id`, `root`, `paths`, `master_limit`, `config` (cached; `reload()`), `store` (lazy `StateStore`), `artifact_spec(name)`, `artifact_path(name) -> Path`, `source_path(source: str) -> Path | None`, `input_path(name) -> Path | None`, `input_exists(name) -> bool`, `input_hash(name) -> str | None`, `artifact_hash(name) -> str | None`.

- [ ] **Step 1: Write the fakes and the failing tests**

`engine/tests/unit/fakes.py` (shared by Tasks 10 to 13):

```python
"""Fake tasks for orchestrator tests. They write small text files."""
from __future__ import annotations

from lychnia.orchestrator.artifacts import ArtifactSpec
from lychnia.orchestrator.task import Gate, Resource, Task

FAKE_ARTIFACTS = {a.name: a for a in [
    ArtifactSpec("x.txt", "work/x.txt"),
    ArtifactSpec("y.txt", "work/y.txt"),
    ArtifactSpec("z.txt", "work/z.txt"),
    ArtifactSpec("p.txt", "work/p.txt"),
    ArtifactSpec("given.txt", "work/given.txt", providable=True),
]}


class MakeX(Task):
    name = "make_x"
    inputs = ("config:cut",)
    outputs = ("x.txt",)
    resource = Resource.LIGHT
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return cfg.cut_fingerprint

    def run(self, ctx):
        ctx.output("x.txt").write_text("x", encoding="utf-8")


class MakeY(Task):
    """Gated: its consumers wait for approval of y.txt."""
    name = "make_y"
    inputs = ("x.txt",)
    outputs = ("y.txt",)
    resource = Resource.CPU_HEAVY
    gate = Gate.A

    def fingerprint(self, cfg):
        return "y"

    def run(self, ctx):
        ctx.output("y.txt").write_text("y", encoding="utf-8")


class MakeZ(Task):
    name = "make_z"
    inputs = ("y.txt", "given.txt")
    outputs = ("z.txt",)
    resource = Resource.CPU_HEAVY
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "z"

    def run(self, ctx):
        ctx.output("z.txt").write_text("z", encoding="utf-8")


class MakeP(Task):
    """On demand only, like `plan`."""
    name = "make_p"
    inputs = ("x.txt",)
    outputs = ("p.txt",)
    resource = Resource.LIGHT
    gate = Gate.A
    on_demand = True

    def fingerprint(self, cfg):
        return "p"

    def run(self, ctx):
        ctx.output("p.txt").write_text("p", encoding="utf-8")


class NeedsP(Task):
    name = "needs_p"
    inputs = ("p.txt",)
    outputs = ("z.txt",)
    resource = Resource.GPU
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "np"

    def run(self, ctx):
        ctx.output("z.txt").write_text("z", encoding="utf-8")


FAKE_TARGETS = {"all": ("make_z",), "xy": ("make_x", "make_y")}
```

Add to `engine/tests/conftest.py`:

```python
MINIMAL_TOML = """[meta]
date = "2026-09-06"
slug = "prueba"
[sources]
master = "input/audio/m.mkv"
cam_a = "input/cam-wide/a.mkv"
[cut]
start = 100.0
end = 200.0
"""


@pytest.fixture
def make_project(tmp_path):
    """Create a minimal project folder; returns a factory taking optional toml text."""
    def _make(toml_text: str = MINIMAL_TOML, name: str = "2026-09-06_prueba"):
        root = tmp_path / name
        root.mkdir(parents=True, exist_ok=True)
        (root / "project.toml").write_text(toml_text, encoding="utf-8")
        return root
    return _make
```

`engine/tests/unit/test_graph.py`:

```python
import pytest

from lychnia.orchestrator.artifacts import ARTIFACTS, is_config, is_source
from lychnia.orchestrator.graph import TARGETS, TaskGraph
from tests.unit.fakes import FAKE_TARGETS, MakeP, MakeX, MakeY, MakeZ, NeedsP


def test_registry_has_the_spec_names():
    for name in ["transcript.srt", "transcript.tsv", "camera_health.txt", "camera_plan.json", "silences.raw.txt",
                 "outline.md", "callouts.toml", "callouts.ass", "callouts_render.ass", "control_sheets.txt",
                 "segments.txt", "preview.mp4", "final.mp4", "final.srt", "shorts.txt", "background.png",
                 "background-prompt.md", "thumbnail.jpg", "thumbnail-1280.jpg", "youtube.md",
                 "shorts-metadata.md", "blog.src.mdx", "blog.mdx"]:
        assert name in ARTIFACTS, name
    assert ARTIFACTS["callouts.toml"].providable and not ARTIFACTS["callouts.ass"].providable
    assert ARTIFACTS["blog.src.mdx"].path == "blog/{slug}.src.mdx"
    assert is_source("source:master") and is_config("config:cut") and not is_source("x.txt")


def test_composite_targets_match_the_spec():
    assert TARGETS["prepare"] == ("transcribe", "camera_health")
    assert TARGETS["gate_a"] == ("callouts", "control_frames")
    assert TARGETS["video"] == ("segments", "preview")
    assert TARGETS["content"] == ("subtitles", "thumbnail", "blog")
    assert TARGETS["deliver"] == ("render", "shorts")


def test_producers_and_dependencies():
    g = TaskGraph([MakeX(), MakeY(), MakeZ()])
    assert g.producer_of("y.txt").name == "make_y"
    assert g.producer_of("given.txt") is None
    assert g.producer_of("config:cut") is None
    assert [t.name for t in g.dependencies(g.tasks["make_z"])] == ["make_y"]


def test_closure_is_topological_and_skips_on_demand_producers():
    g = TaskGraph([MakeX(), MakeY(), MakeZ(), MakeP(), NeedsP()])
    assert [t.name for t in g.closure(["make_z"])] == ["make_x", "make_y", "make_z"]
    assert [t.name for t in g.closure(["needs_p"])] == ["needs_p"]          # make_p only on demand
    assert [t.name for t in g.closure(["make_p"])] == ["make_x", "make_p"]  # explicit request includes it


def test_resolve_target_accepts_composites_and_single_tasks():
    g = TaskGraph([MakeX(), MakeY(), MakeZ()], targets=FAKE_TARGETS)
    assert [t.name for t in g.resolve_target("all")] == ["make_x", "make_y", "make_z"]
    assert [t.name for t in g.resolve_target("xy")] == ["make_x", "make_y"]
    assert [t.name for t in g.resolve_target("make_y")] == ["make_x", "make_y"]
    with pytest.raises(KeyError):
        g.resolve_target("nope")


def test_duplicate_producer_is_rejected():
    class Other(MakeX):
        name = "other"
    with pytest.raises(ValueError):
        TaskGraph([MakeX(), Other()])
```

`engine/tests/unit/test_project.py`:

```python
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS


def test_project_paths_config_and_store(make_project):
    root = make_project()
    p = Project(root, artifacts=FAKE_ARTIFACTS)
    assert p.id == "2026-09-06_prueba"
    assert p.config.duration == 100.0
    assert p.artifact_path("x.txt") == root / "work" / "x.txt"
    assert p.store.get_artifact("x.txt") is None
    assert (root / ".lychnia" / "state.sqlite").exists()


def test_inputs_of_the_three_kinds(make_project):
    root = make_project()
    p = Project(root, artifacts=FAKE_ARTIFACTS)
    assert p.input_exists("config:cut") and not p.input_exists("config:shorts")
    assert p.input_hash("config:cut") is None
    assert not p.input_exists("source:master")
    (root / "input" / "audio").mkdir(parents=True)
    (root / "input" / "audio" / "m.mkv").write_bytes(b"m")
    assert p.input_exists("source:master")
    assert p.input_hash("source:master").startswith("sha256:")
    assert p.source_path("cam_b") is None and not p.input_exists("source:cam_b")
    assert not p.input_exists("x.txt") and p.artifact_hash("x.txt") is None
    p.artifact_path("x.txt").parent.mkdir(parents=True)
    p.artifact_path("x.txt").write_text("x", encoding="utf-8")
    assert p.input_exists("x.txt") and p.artifact_hash("x.txt") == p.input_hash("x.txt")


def test_slug_in_paths_and_reload(make_project):
    from lychnia.orchestrator.artifacts import ARTIFACTS
    root = make_project()
    p = Project(root)
    assert p.artifact_path("blog.src.mdx") == root / "blog" / "prueba.src.mdx"
    (root / "project.toml").write_text((root / "project.toml").read_text().replace('"prueba"', '"otro"'), encoding="utf-8")
    assert p.config.meta.slug == "prueba"     # cached
    p.reload()
    assert p.config.meta.slug == "otro"
    assert ARTIFACTS["final.mp4"].path == "video/final.mp4"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_graph.py tests/unit/test_project.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/orchestrator/artifacts.py`**

```python
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
```

- [ ] **Step 4: Write `engine/lychnia/orchestrator/task.py`**

```python
"""A graph node (spec §4). One subclass per row of the task table (§5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from lychnia.orchestrator.context import Context
    from lychnia.project.config import ProjectConfig


class Resource(str, Enum):
    GPU = "gpu"
    CPU_HEAVY = "cpu_heavy"
    LIGHT = "light"


class Gate(str, Enum):
    NONE = "none"
    A = "gate_a"
    B = "gate_b"


class Task(ABC):
    name: ClassVar[str]
    inputs: ClassVar[tuple[str, ...]] = ()      # artifact names, "source:x" or "config:section.field"
    outputs: ClassVar[tuple[str, ...]] = ()     # artifact names; outputs[0] carries the registry row
    resource: ClassVar[Resource] = Resource.LIGHT
    gate: ClassVar[Gate] = Gate.NONE
    on_demand: ClassVar[bool] = False           # never run because a consumer needs it (like `plan`)

    @abstractmethod
    def fingerprint(self, cfg: "ProjectConfig") -> str:
        """Deterministic string of the config fields that affect this task."""

    @abstractmethod
    def run(self, ctx: "Context") -> None:
        """Do the work; write every output through `ctx.output(name)`."""
```

- [ ] **Step 5: Write `engine/lychnia/orchestrator/graph.py`**

```python
"""Producers, dependencies, transitive closure and composite targets (spec §5, §6.3)."""
from __future__ import annotations

from collections.abc import Iterable

from lychnia.orchestrator.task import Task

TARGETS: dict[str, tuple[str, ...]] = {
    "prepare": ("transcribe", "camera_health"),
    "gate_a": ("callouts", "control_frames"),
    "video": ("segments", "preview"),
    "content": ("subtitles", "thumbnail", "blog"),
    "deliver": ("render", "shorts"),
}


class TaskGraph:
    def __init__(self, tasks: Iterable[Task], targets: dict[str, tuple[str, ...]] | None = None) -> None:
        self.tasks: dict[str, Task] = {}
        self._producers: dict[str, Task] = {}
        self.targets = TARGETS if targets is None else targets
        for task in tasks:
            if task.name in self.tasks:
                raise ValueError(f"duplicate task name: {task.name}")
            self.tasks[task.name] = task
            for out in task.outputs:
                if out in self._producers:
                    raise ValueError(f"artifact {out} produced by both {self._producers[out].name} and {task.name}")
                self._producers[out] = task

    def producer_of(self, name: str) -> Task | None:
        return self._producers.get(name)

    def dependencies(self, task: Task) -> list[Task]:
        deps: list[Task] = []
        for name in task.inputs:
            producer = self._producers.get(name)
            if producer is not None and not producer.on_demand and producer not in deps:
                deps.append(producer)
        return deps

    def closure(self, names: Iterable[str]) -> list[Task]:
        """Requested tasks and their transitive dependencies, dependencies first."""
        order: list[Task] = []
        seen: set[str] = set()

        def visit(task: Task) -> None:
            if task.name in seen:
                return
            seen.add(task.name)
            for dep in self.dependencies(task):
                visit(dep)
            order.append(task)

        for name in names:
            visit(self.tasks[name])
        return order

    def resolve_target(self, target: str) -> list[Task]:
        if target in self.targets:
            return self.closure(self.targets[target])
        if target in self.tasks:
            return self.closure([target])
        raise KeyError(target)
```

- [ ] **Step 6: Write `engine/lychnia/project/project.py`**

```python
"""One sermon project on disk: config, paths, registry and artifact resolution."""
from __future__ import annotations

from pathlib import Path

from lychnia.orchestrator.artifacts import ARTIFACTS, CONFIG_PREFIX, SOURCE_PREFIX, ArtifactSpec, is_config, is_source
from lychnia.orchestrator.hashing import hash_file
from lychnia.orchestrator.state import StateStore
from lychnia.project.config import ProjectConfig, load_config
from lychnia.project.layout import ProjectPaths


class Project:
    def __init__(self, root: Path, master_limit: float | None = None,
                 artifacts: dict[str, ArtifactSpec] | None = None) -> None:
        self.root = Path(root).resolve()
        self.paths = ProjectPaths(self.root)
        self.master_limit = master_limit
        self.artifacts = ARTIFACTS if artifacts is None else artifacts
        self._config: ProjectConfig | None = None
        self._store: StateStore | None = None

    @property
    def id(self) -> str:
        return self.root.name

    @property
    def config(self) -> ProjectConfig:
        if self._config is None:
            self._config = load_config(self.paths.config_file, self.master_limit)
        return self._config

    def reload(self) -> None:
        self._config = None

    @property
    def store(self) -> StateStore:
        if self._store is None:
            self._store = StateStore(self.paths.state_db)
        return self._store

    # ── artifacts ────────────────────────────────────────────────────────
    def artifact_spec(self, name: str) -> ArtifactSpec:
        return self.artifacts[name]

    def artifact_path(self, name: str) -> Path:
        slug = self.config.meta.slug or self.root.name.partition("_")[2]
        return self.root / self.artifact_spec(name).path.format(slug=slug)

    def source_path(self, source: str) -> Path | None:
        rel = getattr(self.config.sources, source)
        return (self.root / rel) if rel else None

    def input_path(self, name: str) -> Path | None:
        if is_config(name):
            return None
        if is_source(name):
            return self.source_path(name[len(SOURCE_PREFIX):])
        return self.artifact_path(name)

    def input_exists(self, name: str) -> bool:
        if is_config(name):
            return self.config.has_input(name[len(CONFIG_PREFIX):])
        path = self.input_path(name)
        return path is not None and path.exists()

    def input_hash(self, name: str) -> str | None:
        path = self.input_path(name)
        if path is None or not path.exists():
            return None
        return hash_file(path)

    def artifact_hash(self, name: str) -> str | None:
        return self.input_hash(name)
```

- [ ] **Step 7: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_graph.py tests/unit/test_project.py -v`
Expected: 9 PASS.

- [ ] **Step 8: Commit**

```bash
git add engine/lychnia/orchestrator/artifacts.py engine/lychnia/orchestrator/task.py engine/lychnia/orchestrator/graph.py engine/lychnia/project/project.py engine/tests/unit/fakes.py engine/tests/unit/test_graph.py engine/tests/unit/test_project.py engine/tests/conftest.py
git commit -m "feat(engine): artifact registry, task graph with composite targets, Project object"
```

---

### Task 11: Event bus and execution context

**Files:**
- Create: `engine/lychnia/orchestrator/events.py`, `engine/lychnia/orchestrator/context.py`
- Test: `engine/tests/unit/test_events.py`, `engine/tests/unit/test_context.py`

**Interfaces:**
- Consumes: `Project` (Task 10), `Cancelled`, `TaskError` (Task 2).
- Produces: `Event(type: str, payload: dict, t: str)`; `EventBus()` with `subscribe() -> queue.Queue[Event]`, `unsubscribe(q)`, `publish(type, **payload) -> Event`; thread-safe. Event types used by the Engine: `task.started`, `task.progress`, `task.log`, `task.finished`, `task.failed`, `artifact.changed`, `approval.changed`, `config.changed`.
- `Context(project: Project, run_id: int, bus: EventBus, cancel: threading.Event, capabilities: dict | None = None, lang: str | None = None)`: `cfg` (config captured at construction), `paths`, `master_limit`, `task_name` (set by the scheduler), `log(msg: str)`, `progress(pct: float, eta_s: float | None = None)`, `output(name) -> Path` (returns `<final>.partial`, parent dir created, remembered), `commit() -> list[Path]` (renames every partial to its final name; raises `TaskError("task.output_missing", artifact=name)` if a requested partial was never written), `abort()` (deletes partials), `check_cancelled()` (raises `Cancelled`), `log_lines: list[str]`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_events.py`:

```python
import queue
import threading

from lychnia.orchestrator.events import EventBus


def test_publish_reaches_every_subscriber():
    bus = EventBus()
    q1, q2 = bus.subscribe(), bus.subscribe()
    ev = bus.publish("task.started", task="plan", run=1)
    assert ev.type == "task.started" and ev.payload == {"task": "plan", "run": 1} and ev.t
    assert q1.get_nowait() is ev and q2.get_nowait() is ev
    bus.unsubscribe(q2)
    bus.publish("task.log", msg="x")
    assert q1.get_nowait().type == "task.log"
    try:
        q2.get_nowait()
        raise AssertionError("q2 still subscribed")
    except queue.Empty:
        pass


def test_publish_from_threads_is_safe():
    bus = EventBus()
    q = bus.subscribe()
    threads = [threading.Thread(target=lambda: [bus.publish("task.progress", pct=i) for i in range(100)])
               for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert q.qsize() == 400
```

`engine/tests/unit/test_context.py`:

```python
import threading

import pytest

from lychnia.errors import Cancelled, TaskError
from lychnia.orchestrator.context import Context
from lychnia.orchestrator.events import EventBus
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS


def _ctx(make_project):
    project = Project(make_project(), artifacts=FAKE_ARTIFACTS)
    bus = EventBus()
    q = bus.subscribe()
    ctx = Context(project, run_id=7, bus=bus, cancel=threading.Event())
    ctx.task_name = "make_x"
    return ctx, q, project


def test_output_partial_then_commit(make_project):
    ctx, q, project = _ctx(make_project)
    partial = ctx.output("x.txt")
    assert partial.name == "x.txt.partial" and partial.parent.is_dir()
    partial.write_text("x", encoding="utf-8")
    final_paths = ctx.commit()
    assert final_paths == [project.artifact_path("x.txt")]
    assert project.artifact_path("x.txt").read_text(encoding="utf-8") == "x"
    assert not partial.exists()


def test_commit_without_writing_fails(make_project):
    ctx, q, project = _ctx(make_project)
    ctx.output("x.txt")
    with pytest.raises(TaskError) as exc:
        ctx.commit()
    assert exc.value.key == "task.output_missing" and exc.value.params["artifact"] == "x.txt"


def test_abort_removes_partials(make_project):
    ctx, q, project = _ctx(make_project)
    p = ctx.output("x.txt")
    p.write_text("half", encoding="utf-8")
    ctx.abort()
    assert not p.exists() and not project.artifact_path("x.txt").exists()


def test_log_and_progress_publish_events(make_project):
    ctx, q, project = _ctx(make_project)
    ctx.log("hello")
    ctx.progress(42.0, eta_s=10)
    e1, e2 = q.get_nowait(), q.get_nowait()
    assert e1.type == "task.log" and e1.payload == {"task": "make_x", "run": 7, "msg": "hello"}
    assert e2.type == "task.progress" and e2.payload == {"task": "make_x", "run": 7, "pct": 42.0, "eta_s": 10}
    assert ctx.log_lines == ["hello"]


def test_cancellation(make_project):
    ctx, q, project = _ctx(make_project)
    ctx.check_cancelled()
    ctx.cancel.set()
    with pytest.raises(Cancelled):
        ctx.check_cancelled()


def test_config_is_captured_at_start(make_project):
    ctx, q, project = _ctx(make_project)
    assert ctx.cfg.duration == 100.0
    (project.root / "project.toml").write_text(
        (project.root / "project.toml").read_text().replace("end = 200.0", "end = 300.0"), encoding="utf-8")
    project.reload()
    assert project.config.duration == 200.0 and ctx.cfg.duration == 100.0
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_events.py tests/unit/test_context.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/orchestrator/events.py`**

```python
"""In-memory event bus (spec §6.5). The API relays it over WebSocket; the CLI prints it."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict = field(default_factory=dict)
    t: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[queue.Queue[Event]] = []
        self._lock = threading.Lock()

    def subscribe(self) -> "queue.Queue[Event]":
        q: queue.Queue[Event] = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[Event]") -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, type: str, **payload: object) -> Event:
        event = Event(type, dict(payload))
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)
        return event
```

- [ ] **Step 4: Write `engine/lychnia/orchestrator/context.py`**

```python
"""What a task receives when it runs (spec §6.4)."""
from __future__ import annotations

import threading
from pathlib import Path

from lychnia.errors import Cancelled, TaskError
from lychnia.orchestrator.events import EventBus
from lychnia.project.project import Project


class Context:
    def __init__(self, project: Project, run_id: int, bus: EventBus, cancel: threading.Event,
                 capabilities: dict | None = None, lang: str | None = None) -> None:
        self.project = project
        self.cfg = project.config            # captured now; later edits do not affect this run
        self.paths = project.paths
        self.master_limit = project.master_limit
        self.run_id = run_id
        self.bus = bus
        self.cancel = cancel
        self.capabilities = capabilities or {}
        self.lang = lang
        self.task_name = ""
        self.log_lines: list[str] = []
        self._partials: dict[str, tuple[Path, Path]] = {}

    # ── reporting ────────────────────────────────────────────────────────
    def log(self, msg: str) -> None:
        self.log_lines.append(msg)
        self.bus.publish("task.log", task=self.task_name, run=self.run_id, msg=msg)

    def progress(self, pct: float, eta_s: float | None = None) -> None:
        self.bus.publish("task.progress", task=self.task_name, run=self.run_id, pct=pct, eta_s=eta_s)

    def check_cancelled(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()

    # ── outputs ──────────────────────────────────────────────────────────
    def output(self, name: str) -> Path:
        """Path to write `name` to. Renamed to its final name by `commit()`."""
        final = self.project.artifact_path(name)
        final.parent.mkdir(parents=True, exist_ok=True)
        partial = final.with_name(final.name + ".partial")
        self._partials[name] = (partial, final)
        return partial

    def commit(self) -> list[Path]:
        for name, (partial, final) in self._partials.items():
            if not partial.exists():
                self.abort()
                raise TaskError("task.output_missing", artifact=name)
        finals = []
        for partial, final in self._partials.values():
            partial.replace(final)
            finals.append(final)
        self._partials.clear()
        return finals

    def abort(self) -> None:
        for partial, _ in self._partials.values():
            partial.unlink(missing_ok=True)
        self._partials.clear()
```

- [ ] **Step 5: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_events.py tests/unit/test_context.py -v`
Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add engine/lychnia/orchestrator/events.py engine/lychnia/orchestrator/context.py engine/tests/unit/test_events.py engine/tests/unit/test_context.py
git commit -m "feat(engine): event bus and task context with partial outputs and cancellation"
```

---

### Task 12: Derived task statuses and the status board

**Files:**
- Create: `engine/lychnia/orchestrator/status.py`
- Test: `engine/tests/unit/test_status.py`

**Interfaces:**
- Consumes: `TaskGraph`, `Task`, `Gate` (Task 10), `Project` (Task 10), `StateStore` (Task 9), `ARTIFACTS`/`is_source`/`is_config` (Task 10), `t` (Task 2).
- Produces: `State` enum (`MISSING_INPUT`, `BLOCKED`, `READY`, `QUEUED`, `RUNNING`, `DONE`, `STALE`, `FAILED`, `AWAITING_APPROVAL`, `APPROVAL_EXPIRED`, `UNREGISTERED`); `RUNNABLE = {READY, STALE, FAILED, UNREGISTERED}`; `TaskStatus(task: str, state: State, missing: list[str], blocked: list[str], error: str | None, actions: list[tuple[str, dict]])` with `message(lang=None) -> str` and `action_texts(lang=None) -> list[str]`; `full_fingerprint(task, project) -> str`; `derive_status(task, graph, project, store) -> TaskStatus`; `status_board(graph, project, store) -> list[TaskStatus]`; `suggest_actions(task, graph, project, status) -> list[tuple[str, dict]]`.

Decision rules (spec §4.1 plus decision 2 of this plan), in order:

1. Latest run `queued`/`running` → `QUEUED`/`RUNNING`.
2. Any input absent → `MISSING_INPUT` (list). Any present input whose producer has a gate and whose current hash is not the approved hash → `BLOCKED` (list).
3. Any output absent → `FAILED` if the latest run failed, else `READY`.
4. Outputs present, no registry row for `outputs[0]` → `UNREGISTERED`.
5. `inputs_fresh = row.fingerprint == full_fingerprint`; `edited = row.hash != current output hash` (when edited, the store is updated with `mark_edited`).
   - not `inputs_fresh`: gated and approved → `APPROVAL_EXPIRED`; otherwise `STALE`.
   - `inputs_fresh`, gate `NONE` → `DONE`.
   - `inputs_fresh`, gated: `approved_hash == current hash` → `DONE`; approved but different hash → `APPROVAL_EXPIRED`; not approved → `AWAITING_APPROVAL`.

Actions: for each missing input: providable artifact → `action.provide`; `source:` → `action.add_source`; `config:` → `action.fill_config`; produced by a task (on-demand included) → `action.run_task` with that task. For `BLOCKED` → `action.approve` per artifact. `READY`/`STALE`/`FAILED`/`UNREGISTERED` → `action.run_task` (own name). `AWAITING_APPROVAL`/`APPROVAL_EXPIRED` → `action.approve` for `outputs[0]`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_status.py`:

```python
import threading

from lychnia.orchestrator.context import Context
from lychnia.orchestrator.events import EventBus
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.status import State, derive_status, full_fingerprint, status_board
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS, MakeP, MakeX, MakeY, MakeZ, NeedsP


def _setup(make_project, toml=None):
    root = make_project() if toml is None else make_project(toml)
    project = Project(root, artifacts=FAKE_ARTIFACTS)
    graph = TaskGraph([MakeX(), MakeY(), MakeZ(), MakeP(), NeedsP()])
    return project, graph, project.store


def _run(task, project, graph):
    """Execute a fake task the way the scheduler will: run, commit, register outputs."""
    run_id = project.store.start_run(task.name)
    ctx = Context(project, run_id, EventBus(), threading.Event())
    ctx.task_name = task.name
    task.run(ctx)
    ctx.commit()
    fp = full_fingerprint(task, project)
    for name in task.outputs:
        project.store.record_artifact(name, str(project.artifact_path(name)), project.artifact_hash(name), fp, task.name)
    project.store.finish_run(run_id, "done")


def test_missing_config_input_with_action(make_project):
    project, graph, store = _setup(make_project, "[meta]\nslug = \"p\"\n")
    st = derive_status(graph.tasks["make_x"], graph, project, store)
    assert st.state is State.MISSING_INPUT and st.missing == ["config:cut"]
    assert st.actions == [("action.fill_config", {"section": "cut"})]
    assert "cut" in st.message(lang="en")


def test_ready_then_done_then_stale(make_project):
    project, graph, store = _setup(make_project)
    x = graph.tasks["make_x"]
    assert derive_status(x, graph, project, store).state is State.READY
    _run(x, project, graph)
    assert derive_status(x, graph, project, store).state is State.DONE
    (project.root / "project.toml").write_text(
        (project.root / "project.toml").read_text().replace("end = 200.0", "end = 210.0"), encoding="utf-8")
    project.reload()
    st = derive_status(x, graph, project, store)
    assert st.state is State.STALE and st.actions == [("action.run_task", {"task": "make_x"})]


def test_missing_artifact_names_its_producer_and_provider(make_project):
    project, graph, store = _setup(make_project)
    st = derive_status(graph.tasks["make_z"], graph, project, store)
    assert st.state is State.MISSING_INPUT and st.missing == ["y.txt", "given.txt"]
    assert st.actions == [("action.run_task", {"task": "make_y"}), ("action.provide", {"artifact": "given.txt"})]
    st_p = derive_status(graph.tasks["needs_p"], graph, project, store)
    assert st_p.actions == [("action.run_task", {"task": "make_p"})]   # on-demand producer still suggested


def test_gate_flow(make_project):
    project, graph, store = _setup(make_project)
    _run(graph.tasks["make_x"], project, graph)
    y = graph.tasks["make_y"]
    _run(y, project, graph)
    st = derive_status(y, graph, project, store)
    assert st.state is State.AWAITING_APPROVAL and st.actions == [("action.approve", {"artifact": "y.txt"})]
    project.artifact_path("given.txt").write_text("g", encoding="utf-8")
    z = derive_status(graph.tasks["make_z"], graph, project, store)
    assert z.state is State.BLOCKED and z.blocked == ["y.txt"]
    store.approve("y.txt", project.artifact_hash("y.txt"), "andres")
    assert derive_status(y, graph, project, store).state is State.DONE
    assert derive_status(graph.tasks["make_z"], graph, project, store).state is State.READY
    # hand edit after approval: approval expires, artifact marked edited, downstream blocked again
    project.artifact_path("y.txt").write_text("y2", encoding="utf-8")
    assert derive_status(y, graph, project, store).state is State.APPROVAL_EXPIRED
    assert store.get_artifact("y.txt").edited is True
    assert derive_status(graph.tasks["make_z"], graph, project, store).state is State.BLOCKED


def test_upstream_change_expires_approval_without_deleting_anything(make_project):
    project, graph, store = _setup(make_project)
    _run(graph.tasks["make_x"], project, graph)
    _run(graph.tasks["make_y"], project, graph)
    store.approve("y.txt", project.artifact_hash("y.txt"), "andres")
    project.artifact_path("x.txt").write_text("x-changed", encoding="utf-8")
    st = derive_status(graph.tasks["make_y"], graph, project, store)
    assert st.state is State.APPROVAL_EXPIRED
    assert project.artifact_path("y.txt").exists()
    assert store.get_artifact("y.txt").approved_hash is not None


def test_unregistered_and_failed(make_project):
    project, graph, store = _setup(make_project)
    x = graph.tasks["make_x"]
    project.artifact_path("x.txt").parent.mkdir(parents=True)
    project.artifact_path("x.txt").write_text("old", encoding="utf-8")
    assert derive_status(x, graph, project, store).state is State.UNREGISTERED
    project.artifact_path("x.txt").unlink()
    run_id = store.start_run("make_x")
    store.finish_run(run_id, "failed", error="boom")
    st = derive_status(x, graph, project, store)
    assert st.state is State.FAILED and st.error == "boom"
    assert "boom" in st.message(lang="en")
    run_id = store.start_run("make_x")
    assert derive_status(x, graph, project, store).state is State.QUEUED
    store.set_run_status(run_id, "running")
    assert derive_status(x, graph, project, store).state is State.RUNNING


def test_board_lists_every_task_in_graph_order(make_project):
    project, graph, store = _setup(make_project)
    board = status_board(graph, project, store)
    assert [s.task for s in board] == ["make_x", "make_y", "make_z", "make_p", "needs_p"]
    assert board[0].state is State.READY
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_status.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/orchestrator/status.py`**

```python
"""Task status derived on the fly from disk, registry and fingerprints (spec §4.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from lychnia.i18n import t
from lychnia.orchestrator.artifacts import CONFIG_PREFIX, SOURCE_PREFIX, is_config, is_source
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.state import StateStore
from lychnia.orchestrator.task import Gate, Task
from lychnia.project.project import Project


class State(str, Enum):
    MISSING_INPUT = "missing_input"
    BLOCKED = "blocked"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    STALE = "stale"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVAL_EXPIRED = "approval_expired"
    UNREGISTERED = "unregistered"


RUNNABLE = {State.READY, State.STALE, State.FAILED, State.UNREGISTERED}


@dataclass
class TaskStatus:
    task: str
    state: State
    missing: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    error: str | None = None
    actions: list[tuple[str, dict]] = field(default_factory=list)

    def message(self, lang: str | None = None) -> str:
        key = f"status.{self.state.value}"
        if self.state is State.MISSING_INPUT:
            return t(key, lang, items=", ".join(self.missing))
        if self.state is State.BLOCKED:
            return t(key, lang, items=", ".join(self.blocked))
        if self.state is State.FAILED:
            return t(key, lang, error=self.error or "")
        return t(key, lang)

    def action_texts(self, lang: str | None = None) -> list[str]:
        return [t(key, lang, **params) for key, params in self.actions]


def full_fingerprint(task: Task, project: Project) -> str:
    """Task fingerprint plus the hashes of its artifact and source inputs."""
    parts = [task.fingerprint(project.config), f"limit={project.master_limit}"]
    parts += [f"{name}={project.input_hash(name)}" for name in task.inputs if not is_config(name)]
    return "|".join(parts)


def suggest_actions(task: Task, graph: TaskGraph, project: Project, status: TaskStatus) -> list[tuple[str, dict]]:
    actions: list[tuple[str, dict]] = []
    if status.state is State.MISSING_INPUT:
        for name in status.missing:
            if is_config(name):
                actions.append(("action.fill_config", {"section": name[len(CONFIG_PREFIX):].split(".")[0]}))
            elif is_source(name):
                actions.append(("action.add_source", {"source": name[len(SOURCE_PREFIX):]}))
            elif (producer := graph.producer_of(name)) is not None:
                actions.append(("action.run_task", {"task": producer.name}))
            elif project.artifact_spec(name).providable:
                actions.append(("action.provide", {"artifact": name}))
    elif status.state is State.BLOCKED:
        actions += [("action.approve", {"artifact": name}) for name in status.blocked]
    elif status.state in RUNNABLE:
        actions.append(("action.run_task", {"task": task.name}))
    elif status.state in (State.AWAITING_APPROVAL, State.APPROVAL_EXPIRED):
        actions.append(("action.approve", {"artifact": task.outputs[0]}))
    return actions


def derive_status(task: Task, graph: TaskGraph, project: Project, store: StateStore) -> TaskStatus:
    status = _derive(task, graph, project, store)
    status.actions = suggest_actions(task, graph, project, status)
    return status


def _derive(task: Task, graph: TaskGraph, project: Project, store: StateStore) -> TaskStatus:
    run = store.latest_run(task.name)
    if run is not None and run.status in ("queued", "running"):
        return TaskStatus(task.name, State(run.status))

    missing, blocked = [], []
    for name in task.inputs:
        if not project.input_exists(name):
            missing.append(name)
            continue
        producer = graph.producer_of(name)
        if producer is not None and producer.gate is not Gate.NONE:
            rec = store.get_artifact(name)
            if rec is None or rec.approved_hash != project.input_hash(name):
                blocked.append(name)
    if missing:
        return TaskStatus(task.name, State.MISSING_INPUT, missing=missing)
    if blocked:
        return TaskStatus(task.name, State.BLOCKED, blocked=blocked)

    if not all(project.artifact_path(o).exists() for o in task.outputs):
        if run is not None and run.status == "failed":
            return TaskStatus(task.name, State.FAILED, error=run.error)
        return TaskStatus(task.name, State.READY)

    primary = task.outputs[0]
    rec = store.get_artifact(primary)
    if rec is None:
        return TaskStatus(task.name, State.UNREGISTERED)
    current_hash = project.artifact_hash(primary)
    inputs_fresh = rec.fingerprint == full_fingerprint(task, project)
    if rec.hash != current_hash:
        store.mark_edited(primary, current_hash)
    if not inputs_fresh:
        if task.gate is not Gate.NONE and rec.approved_hash is not None:
            return TaskStatus(task.name, State.APPROVAL_EXPIRED)
        return TaskStatus(task.name, State.STALE)
    if task.gate is Gate.NONE:
        return TaskStatus(task.name, State.DONE)
    if rec.approved_hash is None:
        return TaskStatus(task.name, State.AWAITING_APPROVAL)
    if rec.approved_hash == current_hash:
        return TaskStatus(task.name, State.DONE)
    return TaskStatus(task.name, State.APPROVAL_EXPIRED)


def status_board(graph: TaskGraph, project: Project, store: StateStore) -> list[TaskStatus]:
    return [derive_status(task, graph, project, store) for task in graph.tasks.values()]
```

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_status.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/orchestrator/status.py engine/tests/unit/test_status.py
git commit -m "feat(engine): derived task statuses, gates and suggested actions"
```

---

### Task 13: Scheduler with three lanes

**Files:**
- Create: `engine/lychnia/orchestrator/scheduler.py`
- Test: `engine/tests/unit/test_scheduler.py`

**Interfaces:**
- Consumes: everything from Tasks 9 to 12.
- Produces: `LANE_CAPACITY = {Resource.GPU: 1, Resource.CPU_HEAVY: 1, Resource.LIGHT: 4}`; `RunReport(started: list[int], blocked: list[TaskStatus])`; `Scheduler(graph, project, bus, lanes: dict[Resource, int] | None = None, capabilities: dict | None = None, lang: str | None = None)` with `run_target(target: str, wait: bool = False) -> RunReport` (when `wait=False` the report is filled as the coordinator progresses; `report.wait()` blocks), `run_task(name, wait=False) -> RunReport` (single task, even if `on_demand`), `cancel(run_id: int) -> bool`, `active_runs() -> list[int]`, `shutdown()`.

Behaviour: a coordinator thread re-derives statuses after every finished run, launches every task in `RUNNABLE` whose lane has room, and drops from the pending set (reporting it in `blocked`) any task whose missing or blocked inputs are not going to be produced by a pending or active task. Each run: `start_run` (queued) → acquire lane semaphore → `set_run_status(running)`, `task.started` → `task.run(ctx)`; `ctx.commit()`; `record_artifact` per output with `full_fingerprint`; `finish_run(done)`; `task.finished`; `artifact.changed` per output. On `Cancelled`: `ctx.abort()`, `finish_run(cancelled)`, `task.failed` with `reason="cancelled"`. On any other exception: `ctx.abort()`, `finish_run(failed, error=str(exc))`, `task.failed`. Log lines of the context are written to `<project>/.lychnia/logs/<run_id>.log` at the end and the path is stored with the run.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_scheduler.py`:

```python
import threading
import time

from lychnia.orchestrator.events import EventBus
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.scheduler import Scheduler
from lychnia.orchestrator.status import State, derive_status
from lychnia.orchestrator.task import Gate, Resource, Task
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS, FAKE_TARGETS, MakeP, MakeX, MakeY, MakeZ, NeedsP


def _setup(make_project, tasks):
    project = Project(make_project(), artifacts=FAKE_ARTIFACTS)
    graph = TaskGraph(tasks, targets=FAKE_TARGETS)
    bus = EventBus()
    return project, graph, bus, bus.subscribe()


def test_chain_runs_in_order_and_stops_at_the_gate(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeY(), MakeZ()])
    project.artifact_path("given.txt").parent.mkdir(parents=True)
    project.artifact_path("given.txt").write_text("g", encoding="utf-8")
    report = Scheduler(graph, project, bus).run_target("all", wait=True)
    assert len(report.started) == 2
    assert project.artifact_path("x.txt").exists() and project.artifact_path("y.txt").exists()
    assert not project.artifact_path("z.txt").exists()
    assert [s.task for s in report.blocked] == ["make_z"] and report.blocked[0].state is State.BLOCKED
    types = [e.type for e in _drain(q)]
    assert types.index("task.finished") < len(types)
    assert types.count("task.started") == 2 and types.count("task.finished") == 2
    assert "artifact.changed" in types
    store = project.store
    assert store.get_artifact("x.txt").producer == "make_x"
    assert store.latest_run("make_y").status == "done" and store.latest_run("make_y").log_path
    assert derive_status(graph.tasks["make_y"], graph, project, store).state is State.AWAITING_APPROVAL


def test_after_approval_the_rest_runs(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeY(), MakeZ()])
    project.artifact_path("given.txt").parent.mkdir(parents=True)
    project.artifact_path("given.txt").write_text("g", encoding="utf-8")
    sched = Scheduler(graph, project, bus)
    sched.run_target("all", wait=True)
    project.store.approve("y.txt", project.artifact_hash("y.txt"), "andres")
    report = sched.run_target("all", wait=True)
    assert len(report.started) == 1 and report.blocked == []
    assert project.artifact_path("z.txt").exists()


def test_missing_provided_artifact_is_reported_not_run(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeY(), MakeZ()])
    report = Scheduler(graph, project, bus).run_target("all", wait=True)
    assert [s.task for s in report.blocked] == ["make_z"]
    assert report.blocked[0].missing == ["given.txt"]


def test_on_demand_task_runs_only_when_asked(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeP(), NeedsP()])
    sched = Scheduler(graph, project, bus)
    report = sched.run_target("needs_p", wait=True)
    assert not project.artifact_path("p.txt").exists()
    assert report.blocked[0].missing == ["p.txt"]
    report = sched.run_task("make_p", wait=True)
    assert project.artifact_path("p.txt").exists() and len(report.started) == 2   # make_x then make_p


class Slow(Task):
    name = "slow_a"
    inputs = ()
    outputs = ("x.txt",)
    resource = Resource.CPU_HEAVY
    gate = Gate.NONE
    running = 0
    peak = 0
    lock = threading.Lock()

    def fingerprint(self, cfg):
        return "s"

    def run(self, ctx):
        with Slow.lock:
            Slow.running += 1
            Slow.peak = max(Slow.peak, Slow.running)
        time.sleep(0.2)
        with Slow.lock:
            Slow.running -= 1
        ctx.output(self.outputs[0]).write_text("s", encoding="utf-8")


class SlowB(Slow):
    name = "slow_b"
    outputs = ("y.txt",)


def test_cpu_heavy_lane_runs_one_at_a_time(make_project):
    Slow.peak = 0
    project, graph, bus, q = _setup(make_project, [Slow(), SlowB()])
    graph.targets = {"both": ("slow_a", "slow_b")}
    Scheduler(graph, project, bus).run_target("both", wait=True)
    assert Slow.peak == 1


class Forever(Task):
    name = "forever"
    inputs = ()
    outputs = ("x.txt",)
    resource = Resource.LIGHT
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "f"

    def run(self, ctx):
        p = ctx.output("x.txt")
        p.write_text("partial", encoding="utf-8")
        while True:
            ctx.check_cancelled()
            time.sleep(0.02)


def test_cancel_terminates_and_cleans_partials(make_project):
    project, graph, bus, q = _setup(make_project, [Forever()])
    sched = Scheduler(graph, project, bus)
    report = sched.run_target("forever")
    deadline = time.time() + 5
    while not report.started and time.time() < deadline:
        time.sleep(0.01)
    assert sched.cancel(report.started[0])
    report.wait()
    assert project.store.get_run(report.started[0]).status == "cancelled"
    assert not project.artifact_path("x.txt").exists()
    assert not list(project.artifact_path("x.txt").parent.glob("*.partial"))
    assert any(e.type == "task.failed" and e.payload.get("reason") == "cancelled" for e in _drain(q))


class Boom(Task):
    name = "boom"
    inputs = ()
    outputs = ("x.txt",)
    resource = Resource.LIGHT
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "b"

    def run(self, ctx):
        ctx.log("about to fail")
        raise RuntimeError("kaput")


def test_failure_is_recorded_with_log(make_project):
    project, graph, bus, q = _setup(make_project, [Boom()])
    report = Scheduler(graph, project, bus).run_target("boom", wait=True)
    run = project.store.get_run(report.started[0])
    assert run.status == "failed" and "kaput" in run.error
    assert "about to fail" in (project.root / run.log_path).read_text(encoding="utf-8")
    assert derive_status(graph.tasks["boom"], graph, project, project.store).state is State.FAILED


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_scheduler.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/orchestrator/scheduler.py`**

```python
"""Queue with three lanes and a coordinator that walks the graph (spec §6.3, §6.4)."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field

from lychnia.errors import Cancelled
from lychnia.orchestrator.context import Context
from lychnia.orchestrator.events import EventBus
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.status import RUNNABLE, State, TaskStatus, derive_status, full_fingerprint
from lychnia.orchestrator.task import Resource, Task
from lychnia.project.project import Project

LANE_CAPACITY: dict[Resource, int] = {Resource.GPU: 1, Resource.CPU_HEAVY: 1, Resource.LIGHT: 4}


@dataclass
class RunReport:
    started: list[int] = field(default_factory=list)
    blocked: list[TaskStatus] = field(default_factory=list)
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)


@dataclass
class _Active:
    task: Task
    cancel: threading.Event
    thread: threading.Thread


class Scheduler:
    def __init__(self, graph: TaskGraph, project: Project, bus: EventBus,
                 lanes: dict[Resource, int] | None = None, capabilities: dict | None = None,
                 lang: str | None = None) -> None:
        self.graph = graph
        self.project = project
        self.bus = bus
        self.capabilities = capabilities or {}
        self.lang = lang
        self.lanes = {res: threading.Semaphore(n) for res, n in (lanes or LANE_CAPACITY).items()}
        self._active: dict[int, _Active] = {}
        self._lock = threading.Lock()
        self._finished: queue.Queue[int] = queue.Queue()

    # ── public API ───────────────────────────────────────────────────────
    def run_target(self, target: str, wait: bool = False) -> RunReport:
        return self._coordinate(self.graph.resolve_target(target), wait)

    def run_task(self, name: str, wait: bool = False) -> RunReport:
        return self._coordinate(self.graph.closure([name]), wait)

    def cancel(self, run_id: int) -> bool:
        with self._lock:
            active = self._active.get(run_id)
        if active is None:
            return False
        active.cancel.set()
        return True

    def active_runs(self) -> list[int]:
        with self._lock:
            return list(self._active)

    def shutdown(self) -> None:
        for run_id in self.active_runs():
            self.cancel(run_id)
        for run_id in self.active_runs():
            self._active[run_id].thread.join()

    # ── coordinator ──────────────────────────────────────────────────────
    def _coordinate(self, tasks: list[Task], wait: bool) -> RunReport:
        report = RunReport()
        pending = {t.name: t for t in tasks}
        mine: set[int] = set()

        def loop() -> None:
            store = self.project.store
            while pending or mine:
                self.project.reload()
                for name, task in list(pending.items()):
                    status = derive_status(task, self.graph, self.project, store)
                    if status.state in RUNNABLE:
                        pending.pop(name)
                        run_id = self._launch(task)
                        report.started.append(run_id)
                        mine.add(run_id)
                    elif status.state in (State.MISSING_INPUT, State.BLOCKED):
                        needs = status.missing + status.blocked
                        producers = {p.name for n in needs if (p := self.graph.producer_of(n)) is not None}
                        active_names = {a.task.name for rid, a in self._active.items() if rid in mine}
                        if not producers & (set(pending) | active_names):
                            pending.pop(name)
                            report.blocked.append(status)
                    elif status.state not in (State.QUEUED, State.RUNNING):
                        pending.pop(name)          # done, awaiting approval, approval expired
                if not mine:
                    if pending:                    # nothing runnable and nothing running: give up
                        for name, task in list(pending.items()):
                            report.blocked.append(derive_status(task, self.graph, self.project, store))
                        pending.clear()
                    break
                finished = self._finished.get()
                mine.discard(finished)
            report._done.set()

        thread = threading.Thread(target=loop, name="lychnia-coordinator", daemon=True)
        thread.start()
        if wait:
            report.wait()
        return report

    # ── one run ──────────────────────────────────────────────────────────
    def _launch(self, task: Task) -> int:
        store = self.project.store
        log_rel = f".lychnia/logs/{{run}}.log"
        run_id = store.start_run(task.name, self.project.master_limit)
        log_path = self.project.paths.logs / f"{run_id}.log"
        store._run("UPDATE runs SET log_path=? WHERE id=?", (log_path.relative_to(self.project.root).as_posix(), run_id))
        cancel = threading.Event()
        ctx = Context(self.project, run_id, self.bus, cancel, self.capabilities, self.lang)
        ctx.task_name = task.name

        def work() -> None:
            with self.lanes[task.resource]:
                store.set_run_status(run_id, "running")
                self.bus.publish("task.started", task=task.name, run=run_id)
                try:
                    ctx.check_cancelled()
                    task.run(ctx)
                    ctx.commit()
                    fp = full_fingerprint(task, self.project)
                    for name in task.outputs:
                        path = self.project.artifact_path(name)
                        store.record_artifact(name, path.relative_to(self.project.root).as_posix(),
                                              self.project.artifact_hash(name), fp, task.name)
                        self.bus.publish("artifact.changed", artifact=name, producer=task.name, run=run_id)
                    store.finish_run(run_id, "done")
                    self.bus.publish("task.finished", task=task.name, run=run_id)
                except Cancelled:
                    ctx.abort()
                    store.finish_run(run_id, "cancelled")
                    self.bus.publish("task.failed", task=task.name, run=run_id, reason="cancelled")
                except Exception as exc:  # noqa: BLE001 - every failure must be recorded
                    ctx.abort()
                    store.finish_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
                    self.bus.publish("task.failed", task=task.name, run=run_id, reason="error",
                                     error=f"{type(exc).__name__}: {exc}")
                finally:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    log_path.write_text("\n".join(ctx.log_lines) + ("\n" if ctx.log_lines else ""), encoding="utf-8")
                    with self._lock:
                        self._active.pop(run_id, None)
                    self._finished.put(run_id)

        thread = threading.Thread(target=work, name=f"lychnia-{task.name}-{run_id}", daemon=True)
        with self._lock:
            self._active[run_id] = _Active(task, cancel, thread)
        thread.start()
        return run_id
```

Replace the private `store._run(...)` call by passing `log_path` to `start_run` instead: compute the run id first is impossible before the insert, so add to `StateStore` a small public method `set_run_log(run_id: int, log_path: str) -> None` (`UPDATE runs SET log_path=? WHERE id=?`) in `state.py` and call `store.set_run_log(run_id, ...)` here. Remove the unused `log_rel` line.

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_scheduler.py tests/unit/test_state.py -v`
Expected: all PASS. The whole suite must still be green: `cd engine && .venv/bin/pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/orchestrator/scheduler.py engine/lychnia/orchestrator/state.py engine/tests/unit/test_scheduler.py
git commit -m "feat(engine): scheduler with gpu/cpu_heavy/light lanes, gates and cancellation"
```

---

### Task 14: ffmpeg runner with progress, cancellation and `filter_path`

**Files:**
- Create: `engine/lychnia/media/ffmpeg.py`
- Test: `engine/tests/unit/test_ffmpeg.py`

**Interfaces:**
- Consumes: `TaskError`, `Cancelled` (Task 2).
- Produces: `parse_progress_line(line: str) -> tuple[str, str] | None`; `FfmpegResult(command: list[str], stderr_tail: str)`; `run_ffmpeg(args: list[str], *, total_s: float | None = None, on_progress: Callable[[float], None] | None = None, cancel: threading.Event | None = None, ffmpeg_cmd: Sequence[str] = ("ffmpeg",), stderr_lines: int = 50, kill_after_s: float = 5.0) -> FfmpegResult`; `filter_path(p: PurePath | str) -> str`; `KILL_AFTER_S = 5.0`.
- `run_ffmpeg` prepends `-nostdin -hide_banner -nostats -progress pipe:1` to `args`, reads `out_time_us` lines from stdout and calls `on_progress(pct)` (0 to 100, capped) when `total_s` is known; keeps the last `stderr_lines` lines of stderr; on `cancel` set: SIGTERM, wait `kill_after_s`, SIGKILL, then raises `Cancelled`; non-zero exit raises `TaskError("task.ffmpeg_failed", command=cmd, stderr_tail=..., code=rc)`; missing binary raises `TaskError("task.ffmpeg_missing")`.

- [ ] **Step 1: Write the failing tests**

`engine/tests/unit/test_ffmpeg.py`:

```python
import sys
import threading
import time
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from lychnia.errors import Cancelled, TaskError
from lychnia.media.ffmpeg import filter_path, parse_progress_line, run_ffmpeg

FAKE_OK = """import sys, time
for i in range(1, 5):
    print(f"out_time_us={i * 1000000}", flush=True)
    print("progress=continue", flush=True)
    time.sleep(0.02)
print("out_time_us=N/A", flush=True)
print("progress=end", flush=True)
print("a warning line", file=sys.stderr)
"""

FAKE_FAIL = """import sys
for i in range(60):
    print(f"err {i}", file=sys.stderr)
sys.exit(3)
"""

FAKE_FOREVER = """import time
while True:
    print("out_time_us=1000000", flush=True)
    time.sleep(0.02)
"""


def _fake(tmp_path, code):
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(code, encoding="utf-8")
    return (sys.executable, str(script))


def test_parse_progress_line():
    assert parse_progress_line("out_time_us=1500000\n") == ("out_time_us", "1500000")
    assert parse_progress_line("progress=end") == ("progress", "end")
    assert parse_progress_line("garbage") is None


def test_progress_callback_and_result(tmp_path):
    seen = []
    result = run_ffmpeg(["-i", "x"], total_s=4.0, on_progress=seen.append, ffmpeg_cmd=_fake(tmp_path, FAKE_OK))
    assert seen == [25.0, 50.0, 75.0, 100.0]
    assert result.command[-2:] == ["-i", "x"] and "-progress" in result.command and "pipe:1" in result.command
    assert result.stderr_tail == "a warning line"


def test_failure_keeps_the_last_50_stderr_lines(tmp_path):
    with pytest.raises(TaskError) as exc:
        run_ffmpeg(["-i", "x"], ffmpeg_cmd=_fake(tmp_path, FAKE_FAIL))
    err = exc.value
    assert err.key == "task.ffmpeg_failed" and err.params["code"] == 3
    lines = err.stderr_tail.splitlines()
    assert len(lines) == 50 and lines[0] == "err 10" and lines[-1] == "err 59"
    assert err.command[0] == sys.executable


def test_cancel_terminates_the_process(tmp_path):
    cancel = threading.Event()
    threading.Timer(0.1, cancel.set).start()
    t0 = time.time()
    with pytest.raises(Cancelled):
        run_ffmpeg([], cancel=cancel, ffmpeg_cmd=_fake(tmp_path, FAKE_FOREVER))
    assert time.time() - t0 < 4


def test_missing_binary():
    with pytest.raises(TaskError) as exc:
        run_ffmpeg([], ffmpeg_cmd=("definitely-not-ffmpeg-binary",))
    assert exc.value.key == "task.ffmpeg_missing"


def test_filter_path_on_the_three_systems():
    assert filter_path(PureWindowsPath(r"C:\Users\a\callouts.ass")) == r"'C\:/Users/a/callouts.ass'"
    assert filter_path(PurePosixPath("/home/a/callouts.ass")) == "'/home/a/callouts.ass'"
    assert filter_path(PurePosixPath("/Users/a/Library/x.ass")) == "'/Users/a/Library/x.ass'"
    assert filter_path(PurePosixPath("/tmp/a b/x.ass")) == "'/tmp/a b/x.ass'"
    assert filter_path(PurePosixPath("/tmp/a:b/x.ass")) == r"'/tmp/a\:b/x.ass'"
    assert filter_path(PurePosixPath("/tmp/o'k/x.ass")) == r"'/tmp/o\'\''k/x.ass'"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd engine && .venv/bin/pytest tests/unit/test_ffmpeg.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `engine/lychnia/media/ffmpeg.py`**

```python
"""Run ffmpeg with progress and cancellation; escape paths for filter graphs (spec §6.4, §9.2)."""
from __future__ import annotations

import collections
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import PurePath

from lychnia.errors import Cancelled, TaskError

KILL_AFTER_S = 5.0


@dataclass(frozen=True)
class FfmpegResult:
    command: list[str]
    stderr_tail: str


def parse_progress_line(line: str) -> tuple[str, str] | None:
    key, sep, value = line.strip().partition("=")
    return (key, value) if sep else None


def run_ffmpeg(args: list[str], *, total_s: float | None = None,
               on_progress: Callable[[float], None] | None = None,
               cancel: threading.Event | None = None,
               ffmpeg_cmd: Sequence[str] = ("ffmpeg",),
               stderr_lines: int = 50, kill_after_s: float = KILL_AFTER_S) -> FfmpegResult:
    cmd = [*ffmpeg_cmd, "-nostdin", "-hide_banner", "-nostats", "-progress", "pipe:1", *args]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise TaskError("task.ffmpeg_missing", command=cmd) from exc

    tail: collections.deque[str] = collections.deque(maxlen=stderr_lines)

    def drain_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            tail.append(line.rstrip("\r\n"))

    drainer = threading.Thread(target=drain_stderr, daemon=True)
    drainer.start()

    assert proc.stdout is not None
    for line in proc.stdout:
        if cancel is not None and cancel.is_set():
            _terminate(proc, kill_after_s)
            drainer.join()
            raise Cancelled()
        kv = parse_progress_line(line)
        if kv and kv[0] == "out_time_us" and on_progress is not None and total_s:
            try:
                done_s = int(kv[1]) / 1_000_000
            except ValueError:
                continue
            on_progress(min(100.0, round(done_s / total_s * 100, 2)))
    code = proc.wait()
    drainer.join()
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    if code != 0:
        raise TaskError("task.ffmpeg_failed", command=cmd, stderr_tail="\n".join(tail), code=code)
    return FfmpegResult(cmd, "\n".join(tail))


def _terminate(proc: subprocess.Popen, kill_after_s: float) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=kill_after_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def filter_path(p: PurePath | str) -> str:
    """Path token for a filter option value (`subtitles=filename=<token>`).

    Forward slashes on every OS; the token is single-quoted so the filtergraph parser takes it
    literally, and `:` is escaped so the filter's own option parser does not split on it.
    A `'` inside the path closes the quote, escapes the quote and reopens.
    """
    text = PurePath(p).as_posix()
    text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'\\''")
    return f"'{text}'"
```

The two `assert` statements above only narrow Optional types for the type checker (stdout/stderr are pipes by construction); they never carry logic. If the project later adopts a linter rule against `assert`, replace them with `if proc.stdout is None: raise RuntimeError(...)`.

- [ ] **Step 4: Run the tests**

Run: `cd engine && .venv/bin/pytest tests/unit/test_ffmpeg.py -v`
Expected: 6 PASS. The cancel test must finish well under 4 s (the fake prints every 20 ms, so the cancel flag is seen on the next line).

- [ ] **Step 5: Commit**

```bash
git add engine/lychnia/media/ffmpeg.py engine/tests/unit/test_ffmpeg.py
git commit -m "feat(engine): ffmpeg runner with progress, cancellation and filter path escaping"
```

---

### Task 15: i18n static scan, full suite, journal

**Files:**
- Create: `engine/tests/unit/test_i18n_scan.py`
- Modify: `docs/JOURNAL.md`, `README.md` (layout section: add `engine/` and `docs/superpowers/plans/`)

**Interfaces:**
- Produces: a test that fails when code uses an i18n key that does not exist in both catalogs, or when a catalog has a key no code uses (dead strings), or when a Spanish operator string is inlined in `lychnia/`.

- [ ] **Step 1: Write the scan test**

`engine/tests/unit/test_i18n_scan.py`:

```python
"""Every message key used in code exists in es and en; no operator text is inlined."""
import re
from pathlib import Path

from lychnia import i18n

PACKAGE = Path(i18n.__file__).resolve().parents[1]
KEY_RE = re.compile(r"""["'](?:validation|status|action|task|template)\.[a-z0-9_]+["']""")
# accented lowercase words inside string literals are the fingerprint of inlined Spanish prose
SPANISH_RE = re.compile(r"""["'][^"'\n]*\b[a-z]*[áéíóúñ][a-z]*\b[^"'\n]*["']""")
ALLOWED_SPANISH_FILES = set()   # add a relative path here only with a comment explaining why


def _sources() -> list[Path]:
    return [p for p in PACKAGE.rglob("*.py") if ".venv" not in p.parts]


def _used_keys() -> set[str]:
    keys: set[str] = set()
    for src in _sources():
        keys.update(m.strip("\"'") for m in KEY_RE.findall(src.read_text(encoding="utf-8")))
    return keys


def test_every_key_used_in_code_exists_in_both_catalogs():
    used = _used_keys()
    assert used, "the scan found no keys; the regex or the package path is wrong"
    for lang in ("es", "en"):
        catalog = i18n.load_messages(lang)
        missing = sorted(k for k in used if k not in catalog)
        assert not missing, f"keys missing in {lang}.toml: {missing}"


def test_dynamic_status_keys_exist():
    from lychnia.orchestrator.status import State
    for lang in ("es", "en"):
        catalog = i18n.load_messages(lang)
        for state in State:
            assert f"status.{state.value}" in catalog, (lang, state)


def test_no_inlined_spanish_in_code():
    offenders = []
    for src in _sources():
        rel = src.relative_to(PACKAGE).as_posix()
        if rel in ALLOWED_SPANISH_FILES:
            continue
        for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if SPANISH_RE.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, "\n".join(offenders)
```

- [ ] **Step 2: Run the scan and the whole suite**

Run: `cd engine && .venv/bin/pytest -q`
Expected: every test passes (about 80). If `test_no_inlined_spanish_in_code` flags a docstring with an accented word, rewrite that docstring in English (docstrings are developer-facing and must be English anyway).

- [ ] **Step 3: Update `docs/JOURNAL.md`, `docs/ROADMAP.md` and `README.md`**

Append to `docs/JOURNAL.md` under a new heading `## <date>: Engine plan 01 executed`: what landed (one line per task group), the test count, and the next step: plan 02 (text lane) via `superpowers:writing-plans`. In `docs/ROADMAP.md` §2 set the plan 01 row to `plan 01 executed (<date>)`, set plan 02 to `next`, and refresh `Last update`. Add `engine/` (package + tests) to the layout block in `README.md`.

- [ ] **Step 4: Commit**

```bash
git add engine/tests/unit/test_i18n_scan.py docs/JOURNAL.md docs/ROADMAP.md README.md
git commit -m "test(engine): i18n static scan; docs: journal and roadmap for plan 01"
```

---

## Self-review against the spec

| Spec section | Covered by | Notes |
|---|---|---|
| §2 principles 1, 4, 5 | Tasks 4, 12, 14 (no chdir, lists, `/` paths) | principle 2 and 3 are exercised by plan 02 tasks |
| §3 layout, projects outside the repo | Task 8 | `~/Lychnia/projects/` default root arrives with the Engine config in plan 04 |
| §4 domain model, §4.1 statuses | Tasks 9, 10, 12 | plus `blocked`, `unregistered` (decision 2) |
| §5 task table | Task 10 registers every artifact name and composite target; task classes land in plans 02 and 03 | `init` (project creation) is `create_project`/`adopt_project` in Task 8; the CLI/API wrapper comes in plan 04 |
| §5.1 gates | Task 12 (approval hash, expiry, edited plan) and Task 13 (stops at gate) | |
| §5.2 test mode | Task 4 (`master_limit` in `end`, `duration`, fingerprints) | env var `MASTER_LIMIT` is read by the CLI/API in plan 04 |
| §6.1 fingerprints and hashes | Tasks 4, 7, 12 | |
| §6.2 state | Task 9 | rebuild-from-disk is the `unregistered` state |
| §6.3 queue and resources, composite targets | Tasks 10, 13 | |
| §6.4 context, `.partial`, progress, cancellation | Tasks 11, 13, 14 | |
| §6.5 events | Task 11 (`task.*`, `artifact.changed`); `approval.changed` and `config.changed` are published by the API/CLI layer in plan 04 | |
| §7 API and CLI | plan 04 | |
| §7.4 i18n | Tasks 2, 15 | |
| §8.1 project.toml, §8.2 engine config, §8.3 capabilities | Task 4, 6, 8; §8.2 and §8.3 in plans 04 and 03 | |
| §9 migration rules | rules 1 to 4 enforced by the structures here; rule 8 by Task 5 | |
| §11 errors | Tasks 2, 4, 14 | |
| §12 tests: unit, golden (config), i18n | Tasks 1 to 15 | golden plan/callouts/subtitles in plan 02; API tests in plan 04; smoke in plan 03 |
| §14 risks: Windows filter paths, old projects, SQLite locking, TOML edited while running | Tasks 14, 12, 9, 11 (config captured at start) | |

Type consistency checked: `Context.output/commit/abort`, `full_fingerprint(task, project)`, `StateStore.record_artifact(name, path, hash, fingerprint, producer)`, `Project.artifact_path/input_exists/input_hash/artifact_hash`, `TaskGraph.producer_of/closure/resolve_target`, `State`/`RUNNABLE` are used with the same names and argument orders in Tasks 10 to 13. `StateStore.set_run_log` is added in Task 13 and must be implemented in `state.py` (one `UPDATE`).
