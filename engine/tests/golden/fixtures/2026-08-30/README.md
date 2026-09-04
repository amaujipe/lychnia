# Fixtures: sermon 2026-08-30 «Gracia que produce excelencia» (Genesis 8)

Real material from the sermon produced and published on 2026-08-30 in the original repo
(`multimedia-iglesia-tunja`), copied here on 2026-09-04 with Andrés's authorization for
the Engine's *golden tests*. It is the reference sermon because its `proyecto.toml` and its
`callouts.toml` reproduce the approved artifacts shot by shot and byte for byte.

| File | What it is | Used by |
|---|---|---|
| `proyecto.toml` | Full config: meta, sources, sync (A −0.333, B −0.600), cut 557.5→5242.5, 5 shorts, 9 plan phases | config, plan, subtitles, shorts |
| `callouts.toml` | 28 RVR1960 verses, continuous reading Gn 8:1-22, re-readings, outline points and key quotes with anchors | callouts |
| `predica.srt` / `predica.tsv` | Transcript (faster-whisper large-v3) of the whole service, master time | anchoring, subtitles, shorts |
| `silencios.raw.txt` | `silencedetect` output (−42 dB, 0.35 s) over the master: allows running `plan` **without the 5 GB file** | plan |
| `esperado_plan_camaras.txt` / `.json` | The **87 shots approved** at Gate A (A 19 % / B 81 %, drift 0.000 ms) | golden for `plan` |
| `esperado_callouts.ass` | Production `callouts.ass` (300 events, master time), md5 `24c6635e…` | golden for `callouts` |
| `esperado_callouts_render.ass` | The same in output time (−557.5 s), md5 `2d3e97d9…` | golden for `callouts` |

The `[fuentes]` paths point to media that is **not** in the repo (ENTREGA/…); the tests
that need it (segments, render, shorts) are smoke tests and are enabled with the environment
variable that points to a local copy of `proyectos/2026-08-30_…/ENTREGA/`.

File names and TOML keys in this folder are the original pipeline's Spanish identifiers
(`predica.srt`, `proyecto.toml`, `corte.entrada`...). They are kept as-is because they are
the reference produced by the original scripts. The Engine's golden tests load them through
a small legacy adapter (or a converted copy) defined in the implementation plan.
