# Context: where Lychnia comes from and what it has to do

> Written on 2026-09-04 when opening this repo, based on the pipeline that works today in
> `~/Repositorios/multimedia-iglesia-tunja` (hereafter "the original repo"). This document
> is enough to understand the domain without reading that repo; the technical detail of the
> current pipeline is in [CURRENT-PIPELINE.md](CURRENT-PIPELINE.md).

## 1. Who and what for

- **Andrés Jiménez** (amaujipe), software developer, serves on the multimedia team of the
  Iglesia de Tunja (Colombia). He is not a video editor by trade.
- Every Sunday the church records the sermon and publishes: the full video on YouTube, an
  article on the website (Astro, repo `guia-clients/iglesia-de-tunja`, collection `blog`) and
  shorts during the week. The Bible used and projected is **Reina-Valera 1960**.
- Between June and September 2026 a pipeline was built with FFmpeg + Python + whisper,
  orchestrated by `make`, where **Claude Code acted as technical director**: it wrote the
  outline, callouts, metadata and blog post from the transcript, and ran the `make` targets.
- **Lychnia** turns that pipeline into a desktop app that runs on its own, on any PC of the
  church or of a volunteer, with or without internet, with or without a GPU.

## 2. What goes in and what comes out

**In** (one `ENTREGA/` folder per sermon, produced by OBS in a single session):

| Source | What it is | Detail |
|---|---|---|
| Master | Main OBS recording (`.mkv`) | Its **audio** is the good one (M-Audio interface via REAPER). Its video is the switched program; it serves as a sync check. |
| Cam A | Fixed wide shot of the hall (`.mkv`, Source Record) | 1080p30 CFR, silent (digital silence). |
| Cam B | Preacher camera (`.mkv`, Source Record) | 1080p30 CFR, silent. May be missing. |
| Photos | From the service, if any | Thumbnail with a face and blog gallery. |
| `INFO.md` | Filled in by Andrés | Title, preacher, role, passage, notes. Proper names are verified here. |

**Out** (v1 deliverables, "up to delivery"):

| Deliverable | Produced today by |
|---|---|
| `predica-final.mp4` 1080p30 multicam A/B, verses and quotes burned in, normalized audio | scripts |
| `predica-final.srt` trimmed to the cut | scripts |
| 4 to 5 shorts 9:16 cropped to the preacher, with subtitles | scripts |
| `miniatura.jpg` 1920×1080 (AI background + brand text) | scripts + manual background |
| YouTube metadata (titles, description, chapters, tags, pinned comment) | Claude |
| Shorts metadata (schedule, titles, descriptions, hashtags) | Claude |
| Blog post `.mdx` (Summary / Teaching / Application, Astro components) | Claude + scripts |
| Outline (`guion.md`) and callouts (`callouts.toml`) as approvable intermediates | Claude |

Publishing (uploading to YouTube, uploading the thumbnail to R2 with `imageforge`, taking the
`.mdx` to the web repo) **is out of scope for v1** and stays manual.

## 3. How it is produced today (summary; detail in CURRENT-PIPELINE.md)

1. **Wave 0**: transcription with faster-whisper (CPU int8, large-v3, VAD, no context) →
   `predica.{srt,tsv,txt,vtt,json}`; camera health audit (black frames, frozen frames).
2. **Sync**: the cameras come silent; the offset is measured by slide changes or motion
   energy (`t_camera = t_master + offset`, typically A −0.33, B −0.60). The **cut** is decided
   (in/out in master seconds). Everything goes to `proyecto.toml`.
3. **Gate A** (human judgment): outline, **phases** of the camera plan → `planear_camaras.py`
   snaps each cut to the longest real silence and writes `plan_camaras.json`; **callouts**
   in `callouts.toml` (RVR1960 verses, quotes, points, lists, each anchored to a real
   sentence of the SRT) → `gen_callouts.py` → `callouts.ass`. Control frames for review.
4. **Parallel lanes**: video (Phase 1 frame-exact segments on the GPU → preview clip)
   and content (thumbnail, blog post, subtitles, metadata).
5. **Gate B**: review `muestra.mp4` (style, lip-sync, volume).
6. **Delivery**: Phase 2 final render in software (concat + libass + voice chain), shorts,
   shorts metadata.

Two design ideas Lychnia inherits as they are:

- **A single source of truth per sermon**: `proyecto.toml` (meta, sources, sync, cut,
  video, audio, gate_b, shorts, plan.fases). Derived values are not configured. The scripts
  are generic.
- **Parameters ≠ approved artifacts**: the shot plan and the callouts are files that a step
  generates and a person approves; never text pasted into code.

## 4. Hard rules (why they exist)

| # | Rule | What happened when it was not followed |
|---|---|---|
| 1 | Final render in software (libx264); Phase 1 may use the GPU | VAAPI/QSV abort when burning subtitles over a concat (2026-07-05) |
| 2 | Frame-exact with `-frames:v round(dur·30)`, never `-t`; boundaries on the 1/30 s frame grid | Cam B at 30.181 fps accumulated +2.2 s of drift over 33 segments; 66 boundaries off the grid gave −0.103 s of drift (2026-08-23) |
| 3 | A single `.ass` with a single libass filter | Chained PNG overlays: 3 h of render versus 10 min |
| 4 | Times anchored to real data; if the anchor does not exist, the generator dies | Callouts with rough-draft timings ended up as much as 26 min out of place |
| 5 | Verses: every one the preacher reads, complete, RVR1960 verified at the source, no gaps in a continuous reading | Explicit requirement from Andrés; the preacher sometimes misreads and corrects himself |
| 6 | Fonts by internal name (`Merriweather Light 18pt`, `DM Sans 9pt`); measure with PIL at `fs·K` (K = 0.573 / 0.757) | Panels 1.7× wider than the text |
| 7 | `aresample=48000` at the end of the voice chain | loudnorm resamples to 192 kHz and the AAC ended up at 96 kHz (2026-07-26) |
| 8 | Shorts: `-map 0:v -map 1:a` (master audio), crop that follows the preacher, libx264 | QSV produced green blocks with complex filters; Andrés rejected the blur-bg |
| 9 | Sync against the audio used in the render, same kind of seek | Mixing input-seek and output-seek gives false offsets (2026-07-19) |
| 10 | Fingerprints per phase: a config change does not redo the expensive work | Adding a short triggered 20 min of Phase 1; one TOML edit re-transcribed 90 min |

Other style constants: hard A/B cuts, no intro or music; "Proposal C" aesthetic
(gold pill `#D4A843` for verses, blue `#1C73A5` for quotes; translucent white panel;
Merriweather + DM Sans); light thumbnails since 2026-08-23; the thumbnail does **not**
repeat the video title (Pescaseo); canonical voice chain
`pan → highpass 80 → speechnorm → alimiter → loudnorm I=-15 → aresample 192k → alimiter → aresample 48k`
with three knobs per sermon (downmix, delay, LUFS).

## 5. Decisions made for Lychnia (brainstorm 2026-09-03)

| # | Decision | Discarded alternatives |
|---|---|---|
| 1 | Target machines: a **mix** (modest volunteer laptops, Andrés's i9 + Iris Xe, maybe a PC with NVIDIA). The app detects capabilities and degrades. | Design for a single machine |
| 2 | Text without internet: **draft with a local LLM**, and API (Claude) when internet is available. Automatic hybrid. | Defer the texts; always everything local; templates without an LLM |
| 3 | Stack: **Tauri + web UI + Python sidecar**. The engine stays in Python. | PySide6; Electron; local server + browser |
| 4 | v1 scope: **up to delivery**. Publishing stays manual. | Up to publishing; video core only |
| 5 | Models: **light installer + separate model bundle** (USB or download). The app works partially without them. | Giant installer; download only |
| 6 | RVR1960: **ask American Bible Society for permission**; meanwhile, RVR1909 bundled + manual paste of the RVR1960 per verse (current flow, permitted). | Bundle without permission; RVR1909 only |
| 7 | Architecture: **approach A**: Python engine with its own orchestrator and local API (127.0.0.1, per-session token, no CORS); Tauri is the shell. | B: orchestrate in Rust; C: stdio JSON-RPC |
| 8 | The local Writer works **in 10 min chunks** (JSON extraction) + short writing; time anchoring always deterministic; shorts candidates by heuristic. | One prompt with the whole transcript (100 min and degraded text) |
| 9 | Default local model **Qwen3 4B** (Q4_K_M); 8B if there is a dedicated GPU or the user accepts waiting. | 8B only |
| 10 | Language: conversation with Andrés in Spanish; everything in the repo (code, identifiers, docs, specs, commits) in English; operator-facing text (CLI/UI messages, template comments) in Spanish through i18n files, never inline. | Spanish artifacts; English UI |

Decomposition into sub-projects: **Engine → AI Providers → Shell → Distribution**.
Each with its own spec and its own plan.

## 6. Glossary

- **Master**: main OBS recording; its audio is the reference and all "master" times are
  measured on it.
- **Offset** (`off_a`, `off_b`): `t_camera = t_master + offset`. Typically negative.
- **Cut** (`entrada`, `salida`): window of the master that goes into the final video.
- **Output time**: `t_master − cut.start` (the original pipeline calls it `entrada`). Callouts are generated in master time
  (`callouts.ass`) and shifted to output time for the render (`callouts_render.ass`).
- **Gate A / Gate B**: the two human approval points (plan + callouts; preview clip).
- **Phase 1 / Phase 2**: segments per shot (GPU) / final composition (software).
- **Fingerprint**: string that summarizes the part of the config that affects a phase; if it
  does not change, the phase is not redone.
- **Callout**: label burned into the video: verse (lower-third or full screen),
  key quote, outline point or progressive list.
- **Provided artifact**: an artifact no deterministic task generates; a person or the Writer
  supplies it (outline, callouts.toml, phases, shorts, blog source, metadata, background prompt).
