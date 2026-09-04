# Lychnia: instructions for Claude Code

## What this is

Cross-platform desktop app that replaces the sermon pipeline of
`~/Repositorios/multimedia-iglesia-tunja` (Make + scripts + Claude Code as orchestrator)
with its own engine, a local API and a Tauri UI. See `README.md`.

## Read this when starting a session

1. `docs/JOURNAL.md`: what was done last time and what comes next.
2. `docs/CONTEXT.md`: origin, deliverables, hard rules, decisions taken.
3. The spec of the sub-project in progress in `docs/superpowers/specs/`.
4. If the detail of the current pipeline is needed: `docs/CURRENT-PIPELINE.md` and the source
   code in `~/Repositorios/multimedia-iglesia-tunja/recursos/scripts/pipeline/` (versioned).

The Engram memory of the previous project is under the name `multimedia-iglesia-tunja`;
search there with `all_projects=true` if context about decisions from June to September 2026
is missing.

## How Andrés works

- Debate point by point before building: numbered options, a one-line recommendation for
  each. He decides. Then implement end to end and test before reporting.
- Short explanations. If he asks «explain it more but with less text», 5 to 8 lines.
- Language policy (project decision, 2026-09-04): conversation with Andrés in Spanish;
  everything committed to this repo in English: code, identifiers, comments, docs, specs,
  plans, commit messages. Operator-facing text (CLI/UI messages, template comments in
  project.toml and INFO.md) is Spanish by default, served from i18n files
  (`lychnia/i18n/es.toml`, `en.toml`), never inline in code. Spanish operator messages use
  soft voseo («revisá», «aprobalo»), inherited from the original Makefile.
- Never propose versioning the texts of the produced sermons (closed decision).

## Domain hard rules (non-negotiable, learned the hard way)

They are explained in `docs/CONTEXT.md` §4. The ten, one line each:

1. Final render in software (libx264); only Phase 1 (segments) goes through the GPU.
2. Frame-exact (`-frames:v`) and shot boundaries on the 1/30 s frame grid.
3. A single burned-in `.ass` with a single libass filter.
4. Every time is anchored to real data (SRT, silences); the LLM never invents times.
5. Verses: every one that is read, complete, verified RVR1960, no gaps in a continuous reading.
6. Fonts by internal name and libass/PIL calibration (Merriweather 0.573, DM Sans 0.757).
7. `aresample=48000` at the end of the audio chain.
8. Shorts with audio from the master and a full-screen crop on the preacher, never blur.
9. Sync measured against the render's audio, with the same kind of seek.
10. A config change does not redo the expensive work: per-phase fingerprints.

## Code conventions

- Python 3.12 (packaging target with PyInstaller), `pathlib`, `subprocess` with lists
  (never shell), paths with `/` for ffmpeg filters. One codebase for the three operating systems.
- English identifiers everywhere (tasks, artifacts, API routes, CLI commands, TOML keys).
  Domain words follow the glossary in the Engine spec (sermon, master recording, cut,
  camera plan, callouts, outline, preview, fingerprint, provided artifact).
- Tests: unit tests for the orchestrator and fingerprints; *golden tests* against the real
  artifacts of the 2026-08-30 sermon (87-shot plan and `callouts.ass` byte for byte).
- Commits in English, Conventional Commits style (`feat(engine): ...`, `docs: ...`).
