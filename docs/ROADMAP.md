# Roadmap: the whole forest and how each tree is doing

> **Living status board.** Read this first in every session, before `JOURNAL.md`.
> `JOURNAL.md` says what happened each day (chronological); this file says how everything
> stands right now (state). Whoever writes or approves a spec or a plan updates the
> matching row here in the same commit. At the end of every session: JOURNAL (what
> happened) + ROADMAP (how it stands) + memory (pointer).

**States**, in order: `not started` → `brainstorm` → `spec draft` → `spec approved` →
`plan NN written` → `plan NN executed` → `done`. A row can also carry `blocked: <why>`.

**Last update:** 2026-09-04.

## 1. The application in one look

Lychnia is four sub-projects, in this order (decided in the brainstorm of 2026-09-03,
`CONTEXT.md` §5). Each one goes through the same cycle: brainstorm → spec → plans → execution.

| # | Sub-project | What it is | State | Where |
|---|---|---|---|---|
| 1 | **Engine** | Python process: orchestrator, tasks (ffmpeg, whisper, generators), local API on 127.0.0.1, CLI. The "backend". | `spec approved`, `plan 01 written` | spec `superpowers/specs/2026-09-04-engine-design.md`; plans `superpowers/plans/2026-09-04-engine-01-*.md` |
| 2 | **AI providers** | Writer (local Qwen3 by chunks, Claude API), Bible database, person detector, provider selection by capabilities and internet. Lives inside the Engine package. | `brainstorm` (decisions 2, 6, 8, 9 taken; interfaces defined in Engine spec §10) | no spec yet |
| 3 | **Shell** | Tauri desktop app: one codebase for Windows, macOS, Linux. Starts the Engine as a sidecar; web UI consumes the API. Screens: project, board, Gate A, Gate B, delivery. | `brainstorm` (decision 3 taken) | no spec yet |
| 4 | **Distribution** | PyInstaller per OS, `llama-server` as a separate binary, model bundle with manifest, USB import, Tauri installers, CI matrix. | `brainstorm` (decision 5 taken) | no spec yet |

Out of scope for v1 (decided): publishing (YouTube upload, R2, web repo). Stays manual.

## 2. Engine (sub-project 1) in detail

The Engine spec is implemented through four plans. Each plan leaves the test suite green.

| Plan | Scope | State | Golden / smoke evidence |
|---|---|---|---|
| 01 Foundation | package, i18n, errors, `project.toml` model + fingerprints, legacy fixture adapter, tomlkit edits, hashing, layout/discovery/template, SQLite state, artifacts/task/graph, events/context, derived statuses, scheduler, ffmpeg runner, `filter_path` | `plan 01 written` (2026-09-04), awaiting Andrés's confirmation of 8 planning decisions listed at the top of the plan | golden config test on the 2026-08-30 sermon |
| 02 Text lane | `text/srt.py`, anchoring, `text/ass_style.py`, `text/callouts.py`; tasks `plan`, `callouts`, `subtitles`, `blog`, `init`; assistant `srt.search` | `not started` (scope defined in plan 01) | 87 shots; `callouts.ass` byte for byte (CRLF-normalized); `final.srt` |
| 03 Media lane | capabilities, encoders, tasks `transcribe` (faster-whisper), `camera_health`, `control_frames`, `segments`, `preview`, `render`, `shorts` + tracking, `thumbnail`; sync assistants; `WriterManual`, `BibleManual`, `DetectorMedian` | `not started` (scope defined in plan 01) | opt-in smoke with `MASTER_LIMIT=700` on `prueba-render` media; `filter_path` against real ffmpeg |
| 04 API + CLI | FastAPI routes, WebSocket events, token file, Typer CLI, Engine config (`platformdirs`), package-wide i18n scan, minimal CI | `not started` (scope defined in plan 01) | API tests with `TestClient`: 401, `Origin` rejected, provide → approve → status |

Pieces of the Engine spec with no plan step yet (they belong to the plans above; listed so
they are not forgotten):

- `approval.changed` and `config.changed` events (plan 04, published by the API/CLI layer).
- `MASTER_LIMIT` environment variable and `limit` request field (plan 04).
- Default projects root `~/Lychnia/projects/` and `<data>/config.toml` (plan 04).
- Capability detection: encoder probes, GPU vendor, RAM, models, internet (plan 03).
- `INFO.md` templates in the Shell language (plan 01 ships es/en files).

## 3. Other sub-projects: what is already decided, what is open

### AI providers (2)

Decided: hybrid text generation (local draft with Qwen3 4B Q4_K_M, 8B with a dedicated GPU;
Claude API when there is internet); Writer works in 10-minute chunks (JSON extraction) plus
short composition; times are always anchored deterministically; RVR1909 bundled and manual
RVR1960 paste until American Bible Society answers. Interfaces `Transcriber`, `Writer`,
`Bible`, `Detector` fixed in Engine spec §10. Spike results in `spikes/2026-09-03-feasibility.md`.

Open: prompt design per chunk and per artifact (outline, callouts, shorts candidates, YouTube
metadata, blog); how the Writer's output enters as provided artifacts through the API;
`llama-server` lifecycle; person detector algorithm (replace the median-background tracker or
keep it); RVR1960 licence outcome.

**When:** spec after plan 03 of the Engine is executed (the API of §7 must exist for the
Writer to provide artifacts).

### Shell (3)

Decided: Tauri + web UI + Python sidecar; Engine prints `{"port", "token"}` on stdout;
no CORS, `Origin` rejected; screens for Gate A (plan + callouts + control frames) and
Gate B (preview). Operator-facing language Spanish by default via the Engine's i18n.

Open: UI framework (not chosen), screen flow and mockups, how the operator edits
`project.toml` from the UI (form per section using `PUT /config`), how hand edits of
`camera_plan.json` are done (external editor vs. in-app), progress and log presentation,
how a volunteer imports the `input/` folder.

**When:** spec after plan 04 of the Engine (the real API and events drive the screens).

### Distribution (4)

Decided: light installer + separate model bundle (USB or download); the app works partially
without models; PyInstaller build verified feasible (397 MB, standalone; spike b).

Open: CI matrix per OS, code signing (Windows SmartScreen, macOS notarization), update
mechanism, model manifest format, USB import UX, ffmpeg bundling per OS.

**When:** spec after the Shell works end to end on Andrés's machine.

## 4. Open questions and pending work outside the code

| Item | Owner | State |
|---|---|---|
| Email to licensing@americanbible.org (cc contacto@sbcol.org) for the RVR1960 text; draft in `abs-rvr1960-permission-request.md`, bracketed data still missing | Andrés | pending |
| Confirm by hand at sic.gov.co that «Lychnia» is not a registered mark in Colombia | Andrés | pending |
| Push the local commits to `github.com/amaujipe/lychnia` | Andrés | pending |
| Which target machines exist for real (volunteer laptops, a PC with NVIDIA?) to size capability detection and defaults | Andrés | open |
| Confirm the 8 planning decisions at the top of plan 01 and choose the execution mode | Andrés | open |

## 5. How to update this file

- Change the `State` cell of the row you touched; add the date in `Last update`.
- A new spec or plan adds its path to the `Where` column the day it is written.
- Move an item out of §4 only when it is done; write the outcome in `JOURNAL.md`.
- Never delete rows to make it shorter; mark them `done`.

Enforcement (2026-09-04), so this file cannot go stale by accident:

- `tools/check_roadmap.py` fails when a spec or plan is not mentioned here, when a reference
  points to a missing file, or when `Last update` is older than the newest commit under
  `docs/superpowers/`. It runs in the pytest suite (`engine/tests/unit/test_roadmap_consistency.py`).
- Claude Code hooks in `.claude/settings.json` (scripts in `tools/hooks/`): `SessionStart`
  injects this file into the model context; `PreToolUse` denies a `git commit` that touches
  `docs/superpowers/` without this file or with an inconsistent roadmap; `Stop` blocks the end
  of a turn when commits made in the session touched working files but `JOURNAL.md` and this
  file did not change (at most three reminders per session, then a warning).
- Pending (Andrés's decision): a repo-level git `pre-commit` hook with the same rule, for
  commits made outside Claude Code.
