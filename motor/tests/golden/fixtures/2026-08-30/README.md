# Fixtures — prédica 2026-08-30 «Gracia que produce excelencia» (Génesis 8)

Material real de la prédica producida y publicada el 2026-08-30 en el repo original
(`multimedia-iglesia-tunja`), copiado aquí el 2026-09-04 con autorización de Andrés para
los *golden tests* del Motor. Es la prédica de referencia porque su `proyecto.toml` y su
`callouts.toml` reproducen plano por plano y byte a byte los artefactos aprobados.

| Archivo | Qué es | Lo usa |
|---|---|---|
| `proyecto.toml` | Config completa: meta, fuentes, sync (A −0.333, B −0.600), corte 557.5→5242.5, 5 shorts, 9 fases del plan | config, plan, subtítulos, shorts |
| `callouts.toml` | 28 versículos RVR1960, lectura corrida Gn 8:1-22, relecturas, puntos y frases con anclas | callouts |
| `predica.srt` / `predica.tsv` | Transcripción (faster-whisper large-v3) del servicio completo, tiempo de maestro | anclaje, subtítulos, shorts |
| `silencios.raw.txt` | Salida de `silencedetect` (−42 dB, 0.35 s) sobre el maestro: permite correr `plan` **sin el archivo de 5 GB** | plan |
| `esperado_plan_camaras.txt` / `.json` | Los **87 planos aprobados** en el Gate A (A 19 % / B 81 %, deriva 0.000 ms) | golden de `plan` |
| `esperado_callouts.ass` | `callouts.ass` de producción (300 eventos, tiempo de maestro), md5 `24c6635e…` | golden de `callouts` |
| `esperado_callouts_render.ass` | El mismo en tiempo de salida (−557.5 s), md5 `2d3e97d9…` | golden de `callouts` |

Las rutas de `[fuentes]` apuntan a medios que **no** están en el repo (ENTREGA/…); los
tests que los necesitan (segmentos, render, shorts) son de humo y se activan con la variable
de entorno que apunte a una copia local de `proyectos/2026-08-30_…/ENTREGA/`.
