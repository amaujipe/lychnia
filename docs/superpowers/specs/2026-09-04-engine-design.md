# Spec: Lychnia Engine (sub-project 1)

**Date:** 2026-09-04 · **Status:** Draft for review by Andrés
**Amended 2026-09-04** after plan 01: `scheduler.failed` event (§6.5); `silences.raw.txt` path (§5).
**Prior context:** [CONTEXT.md](../../CONTEXT.md) (decisions), [CURRENT-PIPELINE.md](../../CURRENT-PIPELINE.md)
(what gets migrated), [spikes](../../spikes/2026-09-03-feasibility.md) (feasibility).

## 1. What the Engine is and is not

The Engine is the Python process that does all of Lychnia's work: it knows which tasks
exist, in what order they run, what is done, what is missing and what needs approval; it
runs ffmpeg, whisper and the generators; and it exposes all of that through a **local API**
for the desktop shell and through a **CLI** for operating it without a UI. It replaces the
`Makefile` of the original repo and Claude Code as the orchestrator.

**In scope for this sub-project:**

- Orchestrator: task graph, fingerprints, persistent state, gates, execution queue with
  per-resource limits, progress and cancellation.
- Migration of the pipeline scripts into generic modules without global state.
- Local API (HTTP + WebSocket on `127.0.0.1`, per-session token) and an equivalent CLI.
- Project configuration (`project.toml`) with reading and comment-preserving editing.
- Machine capability detection (encoders, GPU, RAM, installed models, internet).
- Provider interfaces (Transcriber, Writer, Bible, Detector) with the **manual**
  implementation of each: a person supplies the artifact. The only real implementation
  included is the faster-whisper Transcriber, because it already exists.
- Internationalization of operator-facing text (Spanish by default, English shipped).
- Tests: unit, golden against the 2026-08-30 sermon, and smoke with local media.

**Out of scope** (sub-projects 2, 3 and 4): local or API LLM, Bible database, person
detection, Tauri shell, installers, model bundle, publishing (YouTube, R2, web repo).

## 2. Principles it inherits

1. One source of truth per sermon: `project.toml`. Derived values are never configured.
2. Parameters are not approved artifacts. What gets approved (camera plan, callouts) is a
   file that one step generates, a person approves and another step consumes. It is never
   regenerated silently.
3. Times are anchored to real data. If an anchor does not exist, the task fails with a
   message that names it.
4. A configuration change does not redo expensive work: fingerprints per task.
5. One codebase for the three operating systems: `pathlib`, `subprocess` with argument
   lists, `/` paths for ffmpeg filters, no `os.chdir`, no shell.
6. The ten hard rules in [CLAUDE.md](../../../CLAUDE.md) are enforced in the corresponding
   tasks and verified by tests.

## 3. Repo layout after this sub-project

```
lychnia/
├── engine/
│   ├── pyproject.toml               # package `lychnia`, Python 3.12
│   ├── lychnia/
│   │   ├── cli.py                   # `lychnia …` (Typer)
│   │   ├── api/                     # FastAPI: routes, WebSocket, authentication
│   │   ├── orchestrator/            # graph, task, fingerprint, state, queue, events
│   │   ├── project/                 # config (pydantic + tomlkit), input discovery, layout
│   │   ├── tasks/                   # one class per graph task (§5)
│   │   ├── media/                   # ffmpeg/ffprobe, encoders, voice chain, progress, capabilities
│   │   ├── text/                    # srt, anchoring, ASS style, callouts, final subtitles
│   │   ├── providers/               # interfaces + manual implementations + faster-whisper
│   │   ├── i18n/                    # es.toml (default), en.toml: operator-facing strings
│   │   └── resources/               # brand fonts, project.toml template, INFO.md template
│   └── tests/
│       ├── unit/                    # no ffmpeg, no media
│       ├── golden/                  # 2026-08-30 fixtures: TOMLs, SRT, expected plan and .ass
│       └── smoke/                   # opt-in: real media bounded with MASTER_LIMIT
├── app/                             # reserved (sub-project 3)
└── docs/
```

Sermon projects live **outside the repo**, under a root the operator chooses (default
`~/Lychnia/projects/`). Each project has this layout:

```
2026-09-06_slug/
├── input/          audio/  cam-wide/  cam-preacher/  photos/  INFO.md
├── transcript/
├── outline/
├── video/          work/  gate_b/  shorts/
├── youtube/        assets/
├── blog/           images/
├── project.toml
└── .lychnia/       state.sqlite  logs/
```

Projects produced by the original pipeline are frozen and are not opened by Lychnia; the
only bridge is the golden-test fixture set, loaded through a legacy adapter.

## 4. Domain model

| Concept | What it is | Where it lives |
|---|---|---|
| **Project** | One sermon: a folder with `project.toml` and `input/`. Its id is the folder name (`YYYY-MM-DD_slug`). | disk |
| **Config** | The validated `project.toml` plus derived values (`duration`, `frame_count`, `camera_end`, fingerprints). | memory, reloaded when the file changes |
| **Task** | Graph node. Declares `name`, `inputs` (artifacts or config sections), `outputs` (artifacts), `fingerprint(config)`, `resource` (`gpu`, `cpu_heavy`, `light`), `gate` (whether human approval is required before its consumers may run) and `run(ctx)`. | code |
| **Artifact** | File produced by a task or **provided** from outside. Identified by a logical name (`transcript.srt`, `camera_plan.json`) resolved to a path inside the project. | disk + registry |
| **Registry** | Per artifact: content hash, fingerprint it was produced with, who produced it (task, human, writer), when, and whether it is **approved** (with the approved hash). | `.lychnia/state.sqlite` |
| **Run** | One execution of a task: start, end, result, log, progress. | `.lychnia/state.sqlite` + `.lychnia/logs/` |
| **Capabilities** | What this machine can do: tested encoders, GPU and vendor, RAM, threads, installed models, internet. | memory, recomputed at startup and on demand |

### 4.1 Task status (derived, not stored)

Computed on the fly by comparing registry, fingerprints and files on disk:

- `missing_input`: an input does not exist (with the list of what is missing and who produces it).
- `ready`: all inputs exist and their producers are approved if they have a gate.
- `done`: outputs exist, fingerprint matches and input hashes have not changed.
- `stale`: done, but an input or the fingerprint changed.
- `running` / `failed` (with the error of the last run).
- `awaiting_approval`: done and gated, but nobody approved it.
- `approval_expired`: approved, but an upstream input changed. **The approval is not deleted
  and nothing is regenerated**; the operator is warned.

The status board (`lychnia status`, `GET /projects/{id}/status`) is the list of tasks with
their status and the suggested action, the equivalent of today's `make estado`.

## 5. The task graph

Translation of the `Makefile`. Each row is a class in `lychnia/tasks/`.

| Task | Inputs | Outputs | Fingerprint | Resource | Gate | Notes |
|---|---|---|---|---|---|---|
| `init` | `input/` | `project.toml` | none | light | none | Discovers sources; fills date and slug; never touches a TOML that already has sources. |
| `transcribe` | `sources.master` | `transcript.srt`, `.tsv`, `.txt`, `.vtt`, `.json` | master hash | `cpu_heavy` (faster-whisper) or `gpu` (whisper-cli) | none | A config change **never** re-transcribes. Loop detector and fallback. |
| `camera_health` | `sources.cam_a`, `sources.cam_b` | `camera_health.txt` | camera hashes | light | none | One pass per camera, one report. |
| `plan` | `plan.phases`, `plan.closing_a`, `cut`, `sources.master`, `audio.downmix` | `camera_plan.json`, `video/work/silences.raw.txt` | phases + cut + downmix | light | **Gate A** | Runs **on demand only** (never by dependency). Silence cache keyed by master hash. |
| `callouts` | `callouts.toml` (provided), `outline.md` (provided), `transcript.srt`, `cut_fingerprint` | `callouts.ass`, `callouts_render.ass` | callouts.toml hash + cut_fingerprint | light | **Gate A** | Fails if an anchor does not exist or callouts overlap. |
| `control_frames` | `callouts.ass`, `camera_plan.json`, cameras, `sync` | `gate_a/sheets/*.jpg` | .ass hash + plan hash | light | none | Review material for Gate A. |
| `segments` | `camera_plan.json` (approved), cameras, `video_fingerprint` | `video/work/seg_*.mp4`, `segments.txt` | `video_fingerprint` + plan hash | **gpu** | none | Frame-exact; validates plan, grid, camera end; verifies the sum of durations. |
| `preview` | `segments.txt`, `callouts.ass`, `audio_fingerprint`, `gate_b` | `video/gate_b/preview.mp4` | audio_fingerprint + gate_b + .ass hash | `cpu_heavy` | **Gate B** | Same voice chain as the final render. |
| `render` | `segments.txt`, `callouts_render.ass`, `audio_fingerprint`, **approved** preview | `final.mp4` | audio_fingerprint + .ass hash + segments hash | **cpu_heavy** | none | libx264 always. Prints and records duration, frames, sample rate, LUFS, true peak. |
| `subtitles` | `transcript.srt`, `cut_fingerprint` | `final.srt` | cut_fingerprint | light | none | |
| `shorts` | `shorts`, `shorts_overrides`, `sources.cam_b`, `transcript.tsv`, `audio_fingerprint` | `shorts/<id>.mp4` | per short: its fields + audio_fingerprint | `cpu_heavy` | none | One short at a time; never in parallel with `render`. Redoes only the shorts whose fingerprint changed. |
| `thumbnail` | `assets/background.png` (provided), `meta.passage`, `thumbnail.*` | `thumbnail.jpg`, `thumbnail-1280.jpg` | background hash + fields | light | none | New `[thumbnail]` block in the TOML: `headline` (string or list of lines), `subtitle`, `mode` (`light|dark`), `with_face`, `ai_background`. |
| `blog` | `<slug>.src.mdx` (provided), `publishing.thumbnail_url`, `publishing.youtube_id` | `<slug>.mdx` | src hash + fields | light | none | Resolves `__MINIATURA_URL__` and `__YOUTUBE_ID__` placeholders. Values come from the new `[publishing]` block (the operator writes them when publishing; the R2 URL is deterministic). |

**Provided artifacts** (no task produces them; a person uploads them through the API or the
CLI, and in sub-project 2 the Writer will produce them through the same API): `outline.md`,
`callouts.toml`, `assets/background.png`, `assets/background-prompt.md`, `<slug>.src.mdx`,
`youtube.md`, `shorts-metadata.md`. The TOML sections that Claude writes today are also
"provided": `sync`, `cut`, `plan.phases`, `shorts`, `thumbnail`.

**Assistants** (not graph tasks; helper commands that return numbers for the operator to
write into the TOML): `sync.screen_events`, `sync.screen_offset`, `sync.motion_offset`,
`sync.master_scenes`, `measure.downmix` (L−R in dB to choose `audio.downmix`),
`srt.search` (cues by time range or text, to choose anchors).

### 5.1 The two gates

- **Gate A** covers `plan` and `callouts`. `segments` does not start without an approved
  `camera_plan.json`; `preview` does not start without an approved `callouts.ass`.
- **Gate B** covers `preview`. `render` and `shorts` do not start without an approved preview.
- Approving (`POST …/artifacts/{name}/approve`) stores the approved hash. If the file
  changes afterwards (the plan is regenerated, the callouts TOML is edited), the status
  becomes `approval_expired` and downstream tasks stop being `ready`. Finished work is never
  deleted.
- `camera_plan.json` may be **edited by hand** (as today); the Engine validates grid, gaps
  and short shots when reading it and marks the artifact as "edited" in the registry.

### 5.2 Test mode

`MASTER_LIMIT=<seconds>` (environment variable, or the `limit` field of the `run` request)
bounds cut, plan, segments, render and subtitles to the first N seconds of the master, with
the same semantics as today's `cfg.py`. It is part of the fingerprint so a bounded run is
never mistaken for a full one.

## 6. Orchestrator

### 6.1 Fingerprints

Each task implements `fingerprint(config) -> str`, a deterministic string of the config
fields that affect it (already defined today as `huella_video`, `huella_audio`,
`huella_corte`; here `video_fingerprint`, `audio_fingerprint`, `cut_fingerprint`) plus the
hashes of its input artifacts. It is stored with every output produced. A task is `done`
when its outputs exist and the stored fingerprint equals the current one.

Hash of large files (media): size + mtime + hash of the first and last 8 MB. Hash of small
files (TOML, SRT, JSON, ASS): full SHA-256.

### 6.2 State

SQLite at `<project>/.lychnia/state.sqlite` (stdlib `sqlite3`, WAL). Tables: `artifacts`
(name, path, hash, fingerprint, producer, approved_hash, approved_by, approved_at, edited),
`runs` (task, start, end, status, error, master_limit, log), `events` (run, t, type,
payload). It can be deleted without losing work: the Engine rebuilds it from disk, marking
everything as "unregistered" (the equivalent of the first `make` run on an old project).

### 6.3 Queue and resources

A scheduler with three lanes and capacities `gpu=1`, `cpu_heavy=1`, `light=4`. When asked
to "run up to X" (for example `deliver`), the orchestrator resolves the transitive closure,
discards what is `done`, stops at the first unapproved gate or missing provided artifact,
and enqueues what is `ready` within the resource limits. The two lanes of work (video and
content) run in parallel on their own because they share no resource.

Composite targets (equivalent to today's targets): `prepare` (transcribe + camera_health),
`gate_a` (callouts + control_frames), `video` (segments + preview), `content` (subtitles +
thumbnail + blog), `deliver` (render + shorts).

### 6.4 Running a task

Each task receives a `Context` with the config, resolved paths, capabilities, the test
limit, a `log(msg)` and a `progress(pct, eta_s)`. It writes its outputs to
`<output>.partial` and renames them when finished (the equivalent of `.DELETE_ON_ERROR`).
ffmpeg is launched with `-progress pipe:1` and `-nostats`; the Engine parses `out_time_us`
for progress. Cancelling means terminating the subprocess (SIGTERM, then SIGKILL after 5 s)
and deleting the `.partial` files.

### 6.5 Events

Everything that happens is published as an in-memory event and over WebSocket:
`task.started`, `task.progress`, `task.log`, `task.finished`, `task.failed`,
`artifact.changed`, `approval.changed`, `config.changed`, `scheduler.failed` (a coordinator
failure, not a task failure; carries `error`). The CLI prints them; the UI renders them.

## 7. Local API and CLI

### 7.1 Transport and security

- FastAPI + uvicorn on `127.0.0.1`, random free port.
- At startup the Engine prints a single JSON line to stdout, `{"port": …, "token": …}`,
  and writes it to `<data>/engine.json` with mode 0600 (Tauri reads stdout; the CLI reads
  the file). The token is generated per session (`secrets.token_urlsafe(32)`).
- Every route requires `Authorization: Bearer <token>`; without it, 401. No CORS.
  Requests carrying an `Origin` header are rejected explicitly (blocks the attack from an
  open web page).
- One Engine per user: if `engine.json` points to a live process that responds, the CLI
  uses it; otherwise it starts one.

### 7.2 Routes

```
GET  /system/capabilities               encoders, gpu, ram, threads, models, internet, versions
GET  /projects                          list (configurable root)
POST /projects                          {date, slug} → creates a folder from the template; or {path} → adopts an existing one
GET  /projects/{id}                     summary (meta, sources, cut, duration…)
GET  /projects/{id}/config              TOML as typed JSON + raw text
PUT  /projects/{id}/config              patch by sections; preserves comments (tomlkit); validates
GET  /projects/{id}/status              board: tasks with status and suggested action
POST /projects/{id}/run                 {target | task, limit?} → run ids
POST /projects/{id}/cancel              {run}
GET  /projects/{id}/artifacts           full registry
GET  /projects/{id}/artifacts/{name}    download (text or binary) with ETag = hash
PUT  /projects/{id}/artifacts/{name}    provide (only names declared as providable)
POST /projects/{id}/artifacts/{name}/approve     {hash, who}
DELETE /projects/{id}/artifacts/{name}/approve
POST /projects/{id}/assistants/{name}   sync, measure downmix, search the SRT
GET  /projects/{id}/runs/{run}/log
WS   /events?project=…                  event stream (§6.5)
```

### 7.3 CLI

Mirror of the API with Typer, same semantics as today's targets:

```
lychnia serve                               # starts the Engine (used by Tauri)
lychnia capabilities
lychnia new 2026-09-06 short-title          # creates the project from the template
lychnia status  [-p <project>]
lychnia config  [-p …] [section.field value]
lychnia run prepare|plan|gate_a|video|content|deliver|<task> [-p …] [--limit 700]
lychnia provide callouts.toml path/to/file
lychnia approve camera_plan.json | callouts.ass | preview.mp4
lychnia assist sync.screen_offset --ref … --test … --crop … --t 96
lychnia log <run> [--follow]
```

`-p` defaults to the current folder if it is a project. The CLI starts the Engine in the
background when none is running and shuts it down on exit if it started it.

### 7.4 Internationalization

Command names, flags, API paths and JSON keys are English. Everything the operator reads as
prose is localized:

- CLI output, API error `detail` fields meant for the UI, template comments in
  `project.toml` and `INFO.md`, and `missing_input` instructions come from
  `lychnia/i18n/<lang>.toml`. Spanish (`es`) is the default and ships with the Engine;
  English (`en`) ships too.
- The language is selected by the `language` key of the Engine config (§8.2) or by the
  `LYCHNIA_LANG` environment variable.
- Message keys are English snake_case (`missing_input.callouts_toml`,
  `validation.cut_end_before_start`). Developer logs, the internal message of exceptions,
  code and docs are English.
- Tests assert on message keys, never on Spanish text.

## 8. Configuration

### 8.1 `project.toml`

English keys. The operator-facing comments of the template are Spanish and are generated
from i18n when `lychnia new` writes the file.

```toml
[meta]
date      = "2026-08-30"
slug      = "gracia-que-produce-excelencia"
title     = "Gracia que produce excelencia"
passage   = "Génesis 8"
preacher  = "Américo Ulabarry"
author_id = "seniorPastor"            # seniorPastor | associatePastor | guestSpeaker

[sources]                             # paths relative to the project folder
master = "input/audio/2026-08-30 09-41-53.mkv"
cam_a  = "input/cam-wide/2026-08-30_09-41-53_Panoramica.mkv"
cam_b  = "input/cam-preacher/2026-08-30_09-41-53_Pastor.mkv"   # empty if there was no preacher camera

[sync]                                # t_camera = t_master + offset
offset_a       = -0.333
offset_b       = -0.600
audio_delay_ms = 0                    # >= 0

[cut]                                 # Gate A decision, in master seconds
start = 557.5
end   = 5242.5

[video]                               # optional per-camera filters for Phase 1
# vf_a = "scale=1920:1080:flags=bicubic,setsar=1"
# vf_b = "scale=1920:1080:flags=bicubic,unsharp=5:5:0.3,setsar=1"

[audio]                               # the three knobs of the voice chain (the chain lives in code)
downmix = "dual-mono"                 # dual-mono | left | right
lufs    = -15

[gate_b]                              # preview clip
start    = 3021
duration = 65

[[shorts]]
id      = "s1-logico-o-biblico"
start   = 3013.29
end     = 3055.3
keyword = "bíblica"
title   = "Noé podía bajarse del arca. No se bajó."

[shorts_overrides."s3-dios-en-la-lluvia"]
"-1" = "A Dios en medio de la lluvia aprende a ver a Dios en medio del desastre"

[plan]
closing_a = 26.0                      # last N seconds on the wide shot

[[plan.phases]]
start     = 557.5
end       = 570.0
cam       = "A"
long_shot = 12.5
rest_shot = 0.0
note      = "establishing shot while the passage is announced"

[thumbnail]
headline      = "LÓGICO O BÍBLICO"    # string or list of lines
subtitle      = "Noé esperó la voz, no la evidencia"
mode          = "light"               # light | dark
with_face     = false
ai_background = true

[publishing]                          # written by the operator when publishing (uploading is out of v1)
thumbnail_url = ""                    # deterministic: https://media.iglesiadetunja.org/predicas/<date>/<slug>/miniatura.jpg
youtube_id    = ""
```

Pydantic model with validation (ranges, `cut.end > cut.start`, `audio_delay_ms >= 0`,
downmix in the three options, phases contiguous and aligned to the cut, shorts with all
fields). Read with `tomllib`; edited with `tomlkit` to preserve comments (the commented
template is documentation for the operator). Derived values as today.

### 8.2 Engine configuration (per user)

`<data>/config.toml` (path from `platformdirs`: `~/.local/share/lychnia` on Linux,
`%LOCALAPPDATA%\lychnia` on Windows, `~/Library/Application Support/lychnia` on macOS):
projects root, models folder, forced encoder (`HW_ENCODER`), threads, preferred
transcriber, path to ffmpeg when it is not on PATH, `language` (`es` default).

### 8.3 Capabilities

At startup and on demand: `ffmpeg -encoders` plus a real 1-frame test per encoder
(h264_qsv, h264_nvenc, h264_amf, h264_videotoolbox, libx264); GPU vendor (Vulkan through
`vulkaninfo` when present, otherwise `lspci`/`wmic`/`system_profiler`); RAM and threads;
models present in the models folder with their manifest; internet (HEAD to a known host
with a 2 s timeout). The result drives the encoder choice in `segments` and, in
sub-project 2, the Writer's model choice.

## 9. Script migration

Rules for moving each script of `recursos/scripts/pipeline/` into a `lychnia` module:

1. No global state at import time: no `CFG = Config(...)`, no `CUES = parse()`, no
   `_find_fonts()` walking up directories. Everything comes in as parameters (`config`,
   `paths`, `sources`).
2. No `os.chdir`, no `sys.path.insert`. Paths for ffmpeg filters go through a
   `filter_path(p)` function that returns an escaped path valid on the three systems
   (today it is solved with `relpath` from the repo root; in Lychnia there is no repo root
   at runtime).
3. No `print` as output: `ctx.log()` and typed return values.
4. No `sys.exit` and no `assert`: `ValidationError(field, message, hint)` and
   `TaskError(message)` exceptions.
5. The logic does not change. The guarantee is the golden test: with the 2026-08-30
   fixtures, the plan must produce the same 87 shots and the callouts generator the same
   `.ass` byte for byte.
6. `generar_miniatura` stops being a per-sermon script: texts come from `[thumbnail]`.
7. The brand fonts (`fonts/` for libass, `fonts-portada/` for PIL) and the `project.toml`
   and `INFO.md` templates travel inside the package (`lychnia/resources/`).
8. The legacy fixture set (Spanish file names and TOML keys) is read by a small adapter in
   `tests/golden/legacy.py` that maps old keys to the new config model; production code
   never reads Spanish keys.

Script → module map: `cfg.py` → `project/config.py`; `srt_util.py` → `text/srt.py`;
`estilo_callouts.py` → `text/ass_style.py`; `gen_callouts.py` → `tasks/callouts.py` +
`text/callouts.py`; `planear_camaras.py` → `tasks/plan.py`; `armar_segmentos.py` →
`tasks/segments.py` + `media/encoders.py`; `render_final.py` → `tasks/render.py`;
`clip_muestra.py` → `tasks/preview.py`; `hacer_srt.py` → `tasks/subtitles.py`;
`armar_shorts.py` + `rastrear.py` → `tasks/shorts.py` + `media/tracking.py`;
`frames_control.py` → `tasks/control_frames.py`; `transcribir.py` →
`providers/transcriber_faster_whisper.py` + `tasks/transcribe.py`; sync scripts →
`media/sync.py` (assistants); `salud_camaras.py` → `tasks/camera_health.py`;
`generar_miniatura` → `tasks/thumbnail.py`.

## 10. Providers (interfaces; implementations in sub-project 2)

```python
class Transcriber(Protocol):
    def transcribe(self, audio: Path, out_dir: Path, prefix: str, ctx) -> list[Cue]: ...

class Writer(Protocol):
    def extract(self, chunk: Chunk, ctx) -> ChunkExtract: ...             # 10 min → JSON
    def compose(self, extracts: list[ChunkExtract], request: Request, ctx) -> str: ...

class Bible(Protocol):
    def verse(self, ref: Reference) -> str | None: ...                     # None = not available
    def version(self) -> str: ...

class Detector(Protocol):
    def horizontal_position(self, video: Path, start: float, end: float, ctx) -> list[Node]: ...
```

In this sub-project: `TranscriberFasterWhisper` (real), `WriterManual` (returns "artifact
provided by the operator": the task stays in `missing_input` with an instruction),
`BibleManual` (always `None`: the operator pastes the text into `callouts.toml`, as today)
and `DetectorMedian` (the current algorithm of `rastrear.py`). Provider selection by
capabilities and internet arrives with sub-project 2.

## 11. Errors

- Every validation error names the TOML field, what is wrong and what to do
  (`sync.audio_delay_ms must be >= 0; to advance the audio, correct the camera offsets`).
  The operator-facing text of these messages is localized (§7.4).
- Every task error stores the failing ffmpeg command and the last 50 lines of its stderr
  in the run log.
- A missing provided artifact yields `missing_input` with an instruction text, like the
  `⚠ Falta …` messages of today's Makefile.
- A missing tool (ffmpeg, model) fails when the task starts, not halfway; the capabilities
  already know before.
- No partial output is ever left under its final name.

## 12. Tests

| Level | What | How |
|---|---|---|
| Unit | Graph, derived statuses, fingerprints, gates, resource queue, ffmpeg progress parsing, config validation, `filter_path` on the three OSes (with `pathlib.PureWindowsPath`) | pytest, no media |
| Golden | `plan` → 87 identical shots; `callouts` → `.ass` byte for byte; `subtitles` → expected `.srt`; `config` over the 2026-08-30 example through the legacy adapter | fixtures copied from the original repo: the two example TOMLs, the 2026-08-30 `predica.srt`, reference `plan_camaras.json` and `callouts.ass` |
| API | 401 without token, 200 with token, `Origin` rejected, full cycle provide → approve → status | `TestClient` |
| i18n | Every message key used in code exists in both `es.toml` and `en.toml`; no operator-facing string is inlined in code | pytest, static scan |
| Smoke (opt-in) | `run deliver --limit 700` over the `prueba-render` media: frame-exact (142.5 s = 4275 frames), 48 kHz mono, LUFS and true peak within range, one 1080×1920 short | marker `@pytest.mark.media`, path from an environment variable |
| Portability | The package imports and the API starts on Windows and macOS | CI matrix (sub-project 4 completes it; a minimal workflow lands here) |

## 13. Out of scope and next steps

- **Sub-project 2** (AI providers): `WriterLocal` (llama-server + Qwen3 by chunks),
  `WriterAPI` (Claude), `BibleSQLite` (RVR1909 bundled; RVR1960 if permission is granted),
  `DetectorPerson`, selection by capabilities. All of them enter through the interfaces of
  §10 and provide artifacts through the API of §7.
- **Sub-project 3** (Shell): Tauri starts the Engine as a sidecar, reads the JSON line
  from stdout, and the UI consumes §7. Screens for Gate A (plan + callouts + control
  frames) and Gate B (preview).
- **Sub-project 4** (Distribution): PyInstaller per OS in CI, `llama-server` as a separate
  binary, model bundle with manifest, USB import, Tauri installers.

## 14. Known risks

| Risk | Mitigation |
|---|---|
| Migrating 20 scripts introduces subtle timing regressions | Golden tests byte for byte before touching logic; migrate one script at a time |
| ffmpeg paths and filters on Windows (`C:\`, `:` inside `subtitles=`) | `filter_path` with per-OS unit tests; already solved once in the original repo (docs 17 §4.6) |
| An old project without `.lychnia/` or registry | Rebuild from disk; "unregistered" status until the first run |
| SQLite locked by two processes | One Engine per user (§7.1); WAL |
| The operator edits `project.toml` while a task runs | The task works with the config captured at start; the change marks it `stale` when it finishes |
| Spanish strings sneaking into code | i18n test scans the package for inlined operator-facing text |
