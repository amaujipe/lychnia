# Lychnia

Desktop app (Linux, Windows, macOS) to produce the Sunday sermons of Iglesia de Tunja:
from three OBS recordings to a multi-camera video with verses, subtitles, shorts, thumbnail
and texts for YouTube and the blog. It works offline and with whatever hardware is
available (uses the GPU if there is one, falls back to CPU if not).

**Lychnia** (λυχνία, "lik-NEE-ah") is the Greek word for "lampstand", the one in
Matthew 5:15: the light is not put under a basket "but on a lampstand, and it gives light
to all who are in the house". The app takes the preached message and puts it where
everyone can see it: web, YouTube and social networks.

Repository: https://github.com/amaujipe/lychnia

## Status

**Design phase (September 2026).** The spec of the first sub-project, the Engine, exists.
There is no code yet. The pipeline that will become the app lives and works today in
`~/Repositorios/multimedia-iglesia-tunja` (Make + Python scripts + Claude Code as
orchestrator); Lychnia replaces it with its own orchestrator, a local API and a desktop
interface.

## Layout

```
lychnia/
├── CLAUDE.md                      # how to work in this repo (for Claude Code)
├── README.md                      # this file
├── docs/
│   ├── CONTEXT.md                 # where it comes from, what it produces, hard rules, decisions
│   ├── CURRENT-PIPELINE.md        # the pipeline today: scripts, proyecto.toml, Makefile graph
│   ├── JOURNAL.md                 # memory between sessions
│   ├── spikes/2026-09-03-feasibility.md      # local LLM, packaging, RVR1960 license
│   ├── abs-rvr1960-permission-request.md     # draft email to American Bible Society
│   └── superpowers/specs/
│       └── 2026-09-04-engine-design.md       # ⭐ Engine spec (sub-project 1)
├── engine/                        # (next) Python package `lychnia`: orchestrator + API + tasks + brand resources
└── app/                           # (later) Tauri + web UI
```

## Sub-projects, in order

1. **Engine**: Python orchestrator + local API + tasks migrated from the pipeline. Spec ready.
2. **AI providers**: Transcriber, Writer (local LLM in chunks or API), Bible, Detector.
3. **Shell**: Tauri + web UI with the two Gates as review screens.
4. **Distribution**: per-OS installers, model bundle, hardware detection.

## Resuming with Claude Code

Open a session in this folder. `CLAUDE.md` tells it what to read.
