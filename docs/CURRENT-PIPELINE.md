# The current pipeline: what Lychnia migrates

> State as of 2026-09-04 of the original repo `~/Repositorios/multimedia-iglesia-tunja`
> (commit `39da6d3`). The scripts are versioned in `recursos/scripts/pipeline/` and are
> copied to `<proyecto>/3-guion/` by `make init`. This document is the map for migrating them
> without rereading the repo; when in doubt, the source code rules.

## 1. Script catalog (`recursos/scripts/pipeline/`)

Names below are the original repo's Spanish identifiers; Lychnia uses the English equivalents listed in the Engine spec.

| Script | Role | Inputs | Outputs | Migration notes |
|---|---|---|---|---|
| `cfg.py` | Per-sermon config. Reads `proyecto.toml`, derives `dur`, `nframes`, `fin_cam` (ffprobe), exposes `af_voz()`, `seg()`, fingerprints, `--init`. | `proyecto.toml`, `ENTREGA/` | — | Becomes `project/config.py` (pydantic). Global `CFG` instance on import: remove. |
| `transcribir.py` | faster-whisper (CPU int8, VAD, no context) or whisper-cli GPU (`-mc 0` + VAD). Loop detector (phrase of ≥4 words ×8 in a row or ×20 total) and automatic fallback. Writes srt/vtt/txt/tsv/json. | master | `1-transcripcion/predica.*` | Already generic and free of `CFG`. Becomes the `Transcriber` provider. |
| `salud_camaras.py` | Black frames, frozen frames, reframings per camera (brightness, std, diff at 1 fps, 192×108). | camera | text | Generic. |
| `slide_events.py` `slide_texto.py` `sync_pantalla.py` `sync_movimiento.py` `escena_maestro.py` | Sync of silent cameras by slide changes (sub-frame interpolation) or motion energy; map of which camera is on air in the master. | cameras, master, screen crop | offsets, tables | Manual tools today. In Lychnia v1: "assistants" exposed through API/CLI; the operator writes the offsets. |
| `planear_camaras.py` | A/B plan: walks `[[plan.fases]]`, snaps cuts to the longest nearby silence (`silencedetect -42 dB, 0.35 s`, measured with `-vn`), merges equal shots, closes on A, boundaries on the 1/30 s frame grid, validates. | phases, master | `plan_camaras.json` + table | Becomes task `plan`. Golden: 87 shots from 2026-08-30. |
| `srt_util.py` | `find(ancla, after, nth)` and `find_in` (interpolates inside the cue). Normalizes accents and ñ. Dies if it finds no match. | `predica.srt` | seconds | Global `CUES` module on import: remove. |
| `estilo_callouts.py` | "Proposal C" ASS engine: `verse_lt`, `verse_full`, `quote`, `point`, `list_lt`. Measures with calibrated PIL. | — | ASS events | Generic. Looks for `recursos/marca/fonts` walking up directories: pass an explicit path. |
| `gen_callouts.py` | Reads `callouts.toml` (`[versiculos]`, chained `[[lecturas]]`, `[[callouts]]` verso/verso_full/frase/punto/lista), anchors, checks overlaps and durations, writes `callouts.ass` and `callouts_render.ass` (−entrada). | `callouts.toml`, srt, cut | `.ass` ×2 | Golden: 300 events byte for byte (2026-08-30). |
| `frames_control.py` | One real frame per callout with the `.ass` burned in (`setpts` to master time), 3×3 contact sheets. | `.ass`, plan, cameras | jpg | Visual Gate A/B. |
| `armar_segmentos.py` | Phase 1: one `.mp4` per shot, `-frames:v round(dur·30)`, `-fps_mode cfr`, encoder by `HW_ENCODER` (qsv→nvenc→amf→libx264, probed with 1 frame), validates plan and sum of durations. | plan, cameras, offsets, `vf_a/vf_b` | `_work/seg_*.mp4`, `segs.txt` | GPU resource. |
| `clip_muestra.py` | Gate B: `[gate_b]` clip over the segments + shifted `.ass` + `af_voz`. | segs, `.ass`, master | `_gateB/muestra.mp4` | |
| `render_final.py` | Phase 2: concat + `subtitles=…:fontsdir=…` + `af_voz`, libx264 veryfast crf 20, AAC 160k mono, `-t dur`; prints duration, frames, sample rate, LUFS. | segs, `callouts_render.ass`, master | `predica-final.mp4` | Heavy CPU resource. Always software. |
| `hacer_srt.py` | Shifts by −entrada, trims to the window (also the text of split cues, with a 0.92 margin), discards leftovers <0.8 s, deduplicates. | srt, cut | `predica-final.srt` | |
| `rastrear.py` | Horizontal position of the preacher: background = median of ~70 frames from the whole file; centroid of the difference; smoothing; `expr_crop` with half-open spans. | cam B | nodes (t, x) | Decodes the whole file for the background (~2.5 min). |
| `armar_shorts.py` | 1080×1920: 608×1080 crop that follows the preacher, subtitles from the `.tsv` with callout aesthetic and gold keyword, hook title, final CTA, more opaque panel (`12`), per-cue overrides, `af_voz`, libx264. | `[[shorts]]`, cam B, master, tsv | `shorts/<id>.mp4` | |
| `generar_miniatura.EJEMPLO-*.py` | Light thumbnail: kicker (passage from `[meta]`), power word, gold divider, real italic subtitle, frame; `--fondo-ia`, `--con-rostro` (rembg + corrections), `--oscuro`. Variable fonts from `fonts-portada/` with verified axis order. | background, meta | `miniatura.jpg` + 1280 | **Still per sermon**: FUERZA and SUBTIT are in the code. Move to `[miniatura]` in the TOML. |
| `vercues.py` | Dump cues by time range. | srt | text | Utility. |

Real versioned examples: `proyecto.EJEMPLO-2026-08-30.toml`, `callouts.EJEMPLO-2026-08-30.toml`
(they reproduce, shot by shot and byte for byte, the approved artifacts of that sermon).

## 2. `proyecto.toml` (blocks)

```toml
[meta]     fecha, slug, titulo, pasaje, pastor, autor_id (seniorPastor|associatePastor|guestSpeaker)
[fuentes]  maestro, cam_a, cam_b          # rutas relativas al proyecto; cam_b puede ir vacío
[sync]     off_a, off_b, audio_delay_ms   # t_cam = t_maestro + off; delay ≥ 0
[corte]    entrada, salida                # segundos de maestro
[video]    vf_a, vf_b                     # opcional; defaults scale bicubic / +unsharp
[audio]    mezcla (dual-mono|izquierdo|derecho), lufs
[gate_b]   inicio, duracion
[[shorts]] id, ini, fin, clave, titulo
[shorts_overrides.<id>]  "-1" = "texto"   # cue forzada por posición
[plan]     cierre_a
[[plan.fases]] t_ini, t_fin, cam, dur_larga, dur_descanso, nota
```

Derived (not configured): `dur = salida − entrada`, `nframes = round(dur·30)`,
`fin_cam` by ffprobe. `LIMITE_MASTER=<seg>` limits everything to the first N s for tests.

Fingerprints: `huella_video` (cameras, offsets, vf, entrada, fin), `huella_audio` (master,
mezcla, lufs, delay, entrada, fin), `huella_corte` (entrada, fin).

## 3. The Makefile graph (what the orchestrator replaces)

```
init ────────────► proyecto.toml
proyecto.toml ─|─► predica.srt/.tsv        (transcribir; order-only: un cambio de config NO re-transcribe)
cam A, cam B ────► _salud.txt              (salud_camaras ×2)

[GATE A: humano escribe sync/corte/fases en el TOML; aporta guion.md y callouts.toml]
plan (a pedido) ─► plan_camaras.json       (planear_camaras; NO se regenera por dependencias: es lo aprobado)
callouts.toml + srt + guion.md + huella_corte ─► callouts.ass, callouts_render.ass

CARRIL VIDEO
plan_camaras.json + huella_video + cams ─► _work/segs.txt        (armar_segmentos, GPU)
segs.txt + callouts.ass + huella_audio ──► _gateB/muestra.mp4   (clip_muestra)
[GATE B: humano aprueba la muestra]
segs.txt + callouts_render.ass + huella_audio ─► predica-final.mp4   (render_final, CPU)
TOML[[shorts]] + huella_audio | predica-final.mp4 ─► shorts/.done    (armar_shorts; order-only para no pelear CPU)
shorts/.done ─► shorts-metadata.md         (aportado)

CARRIL CONTENIDO
fondo.png (aportado) + guion.md ─► miniatura.jpg   (generar_miniatura --fondo-ia)
miniatura.jpg ─► .miniatura.url            (imageforge → R2; FUERA de Lychnia v1)
<slug>.src.mdx (aportado) + .miniatura.url ─► <slug>.mdx   (sed de __MINIATURA_URL__ y __YOUTUBE_ID__)
predica.srt + huella_corte ─► predica-final.srt   (hacer_srt)
publicacion-youtube.md                     (aportado)
```

Resource rules: GPU (transcribe if whisper-cli, segments) never two at once; heavy CPU
(final render) one at a time; everything else is light. `make -j4 contenido video` runs
both lanes. `make estado` is the dashboard of what is done and what is missing.

## 4. What Claude Code does today (and what Lychnia must cover with Writer + human)

| Artifact | From | Rules |
|---|---|---|
| `guion.md` | transcript + `INFO.md` | Fact sheet, summary, structure with minutes, verses read, strong quotes, three distinct texts (title / thumbnail / YouTube title: Pescaseo) |
| `[[plan.fases]]` | outline + structure | Phases with long-shot camera, long duration and rest duration |
| `callouts.toml` | transcript + Bible | Verified RVR1960 text (today Bible Gateway); anchors to SRT sentences; `after`/`nth`/`interpolar`; chained readings |
| `[[shorts]]` | transcript + tsv | 30 to 60 s, in/out on silences, end on the strong quote, keyword, hook title |
| `prompt-fondo-miniatura.md` | topic | 3 variants, plain left half, "not a single letter", no rainbows unless called for |
| `publicacion-youtube.md` | transcript | 3 titles (Pescaseo), description with SEOEXTRACTO, ≥3 chapters from 0:00 in output time, tags, pinned comment, pastoral filter |
| `shorts-metadata.md` | shorts | Schedule Tue/Thu/Sat never Sunday, from strongest to weakest hook, title + description + hashtags |
| `<slug>.src.mdx` | transcript | Astro frontmatter, `VerseHighlight` reference only (no literal text), one `EmphasisBox`, Summary/Teaching/Application structure, no CJK, unique slug |

## 5. Original repo environment

Arch Linux, ffmpeg 9 (libass, QSV/VAAPI), `whisper-cli` (whisper.cpp Vulkan) with
`ggml-large-v3.bin` and VAD `ggml-silero-v5.1.2.bin`, `.venv` Python 3.14 with Pillow, numpy,
faster-whisper (CT2 large-v3 model in HF cache, 2.9 GB), rembg. Brand fonts in
`recursos/marca/fonts/` (libass) and `fonts-portada/` (PIL, variable). Visual identity in
`recursos/marca/identidad.md`.
