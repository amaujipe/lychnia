# El pipeline actual — lo que Lychnia migra

> Estado al 2026-09-04 del repo original `~/Repositorios/multimedia-iglesia-tunja`
> (commit `39da6d3`). Los scripts están versionados en `recursos/scripts/pipeline/` y se
> copian a `<proyecto>/3-guion/` con `make init`. Este documento es el mapa para migrarlos
> sin releer el repo; ante la duda, el código fuente manda.

## 1. Catálogo de scripts (`recursos/scripts/pipeline/`)

| Script | Rol | Entradas | Salidas | Notas de migración |
|---|---|---|---|---|
| `cfg.py` | Config por prédica. Lee `proyecto.toml`, deriva `dur`, `nframes`, `fin_cam` (ffprobe), expone `af_voz()`, `seg()`, huellas, `--init`. | `proyecto.toml`, `ENTREGA/` | — | Se vuelve `proyecto/config.py` (pydantic). Instancia global `CFG` al importar: eliminar. |
| `transcribir.py` | faster-whisper (CPU int8, VAD, sin contexto) o whisper-cli GPU (`-mc 0` + VAD). Detector de bucle (frase ≥4 palabras ×8 seguidas o ×20 total) y respaldo automático. Escribe srt/vtt/txt/tsv/json. | maestro | `1-transcripcion/predica.*` | Ya es genérico y sin `CFG`. Se vuelve proveedor `Transcriptor`. |
| `salud_camaras.py` | Negros, congelados, reencuadres por cámara (brillo, std, dif a 1 fps, 192×108). | cámara | texto | Genérico. |
| `slide_events.py` `slide_texto.py` `sync_pantalla.py` `sync_movimiento.py` `escena_maestro.py` | Sincronía de cámaras mudas por cambios de diapositiva (interpolación sub-frame) o energía de movimiento; mapa de qué cámara está al aire en el maestro. | cámaras, maestro, crop de pantalla | offsets, tablas | Herramientas manuales hoy. En Lychnia v1: «asistentes» expuestos por API/CLI, offsets los escribe el operador. |
| `planear_camaras.py` | Plan A/B: recorre `[[plan.fases]]`, imanta cortes al silencio más largo cercano (`silencedetect -42 dB, 0.35 s`, medido con `-vn`), fusiona planos iguales, cierre en A, fronteras a la rejilla de 1/30 s, valida. | fases, maestro | `plan_camaras.json` + tabla | Se vuelve tarea `plan`. Golden: 87 planos de 2026-08-30. |
| `srt_util.py` | `find(ancla, after, nth)` y `find_in` (interpola dentro de la cue). Normaliza tildes y ñ. Muere si no encuentra. | `predica.srt` | segundos | Módulo global `CUES` al importar: eliminar. |
| `estilo_callouts.py` | Motor ASS «Propuesta C»: `verse_lt`, `verse_full`, `quote`, `point`, `list_lt`. Mide con PIL calibrado. | — | eventos ASS | Genérico. Busca `recursos/marca/fonts` subiendo directorios: pasar ruta explícita. |
| `gen_callouts.py` | Lee `callouts.toml` (`[versiculos]`, `[[lecturas]]` encadenadas, `[[callouts]]` verso/verso_full/frase/punto/lista), ancla, verifica solapes y duraciones, escribe `callouts.ass` y `callouts_render.ass` (−entrada). | `callouts.toml`, srt, corte | `.ass` ×2 | Golden: 300 eventos byte a byte (2026-08-30). |
| `frames_control.py` | Un cuadro real por callout con el `.ass` quemado (`setpts` al tiempo maestro), hojas de contacto 3×3. | `.ass`, plan, cámaras | jpg | Gate A/B visual. |
| `armar_segmentos.py` | Fase 1: un `.mp4` por plano, `-frames:v round(dur·30)`, `-fps_mode cfr`, encoder por `HW_ENCODER` (qsv→nvenc→amf→libx264, probado con 1 frame), valida plan y suma de duraciones. | plan, cámaras, offsets, `vf_a/vf_b` | `_work/seg_*.mp4`, `segs.txt` | Recurso GPU. |
| `clip_muestra.py` | Gate B: clip `[gate_b]` sobre los segmentos + `.ass` desplazado + `af_voz`. | segs, `.ass`, maestro | `_gateB/muestra.mp4` | |
| `render_final.py` | Fase 2: concat + `subtitles=…:fontsdir=…` + `af_voz`, libx264 veryfast crf 20, AAC 160k mono, `-t dur`; imprime duración, frames, sample rate, LUFS. | segs, `callouts_render.ass`, maestro | `predica-final.mp4` | Recurso CPU pesado. Software siempre. |
| `hacer_srt.py` | Desplaza −entrada, recorta a la ventana (también el texto de cues partidas, con margen 0.92), descarta restos <0.8 s, deduplica. | srt, corte | `predica-final.srt` | |
| `rastrear.py` | Posición horizontal del pastor: fondo = mediana de ~70 cuadros de todo el archivo; centroide de la diferencia; suavizado; `expr_crop` con tramos semiabiertos. | cam B | nodos (t, x) | Decodifica todo el archivo para el fondo (~2.5 min). |
| `armar_shorts.py` | 1080×1920: crop 608×1080 que sigue al pastor, subtítulos del `.tsv` con estética de callout y palabra clave dorada, título-gancho, CTA final, panel más opaco (`12`), overrides por cue, `af_voz`, libx264. | `[[shorts]]`, cam B, maestro, tsv | `shorts/<id>.mp4` | |
| `generar_miniatura.EJEMPLO-*.py` | Portada clara: kicker (pasaje de `[meta]`), palabra fuerza, divisor dorado, subtítulo itálica real, marco; `--fondo-ia`, `--con-rostro` (rembg + correcciones), `--oscuro`. Fuentes variables de `fonts-portada/` con orden de ejes verificado. | fondo, meta | `miniatura.jpg` + 1280 | **Por prédica todavía**: FUERZA y SUBTIT están en el código. Mover a `[miniatura]` del TOML. |
| `vercues.py` | Volcar cues por rango de tiempo. | srt | texto | Utilidad. |

Ejemplos reales versionados: `proyecto.EJEMPLO-2026-08-30.toml`, `callouts.EJEMPLO-2026-08-30.toml`
(reproducen plano por plano y byte a byte los artefactos aprobados de esa prédica).

## 2. `proyecto.toml` (bloques)

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

Derivados (no se configuran): `dur = salida − entrada`, `nframes = round(dur·30)`,
`fin_cam` por ffprobe. `LIMITE_MASTER=<seg>` acota todo a los primeros N s para pruebas.

Huellas: `huella_video` (cámaras, offsets, vf, entrada, fin), `huella_audio` (maestro,
mezcla, lufs, delay, entrada, fin), `huella_corte` (entrada, fin).

## 3. El grafo del Makefile (lo que el orquestador reemplaza)

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

Reglas de recursos: GPU (transcribir si whisper-cli, segmentos) nunca dos a la vez; CPU
pesado (render final) uno a la vez; lo demás es liviano. `make -j4 contenido video` corre
los dos carriles. `make estado` es el tablero de qué está hecho y qué falta.

## 4. Lo que hace Claude Code hoy (y que Lychnia debe cubrir con Redactor + humano)

| Artefacto | Desde | Reglas |
|---|---|---|
| `guion.md` | transcripción + `INFO.md` | Ficha, resumen, estructura con minutos, versículos leídos, frases fuertes, tres textos distintos (título / portada / título de YouTube: Pescaseo) |
| `[[plan.fases]]` | guion + estructura | Fases con cámara larga, duración larga y de descanso |
| `callouts.toml` | transcripción + Biblia | Texto RVR1960 verificado (hoy Bible Gateway); anclas a frases del SRT; `after`/`nth`/`interpolar`; lecturas encadenadas |
| `[[shorts]]` | transcripción + tsv | 30 a 60 s, entrada/salida en silencios, rematar en la frase fuerte, palabra clave, título-gancho |
| `prompt-fondo-miniatura.md` | tema | 3 variantes, mitad izquierda lisa, «ni una letra», sin arcoíris si no toca |
| `publicacion-youtube.md` | transcripción | 3 títulos (Pescaseo), descripción con SEOEXTRACTO, capítulos ≥3 desde 0:00 en tiempo de salida, tags, comentario fijado, filtro pastoral |
| `shorts-metadata.md` | shorts | Calendario mar/jue/sáb nunca domingo, de mayor a menor gancho, título + descripción + hashtags |
| `<slug>.src.mdx` | transcripción | Frontmatter Astro, `VerseHighlight` solo referencia (sin texto literal), un `EmphasisBox`, estructura Resumen/Enseñanza/Aplicación, sin CJK, slug único |

## 5. Entorno del repo original

Arch Linux, ffmpeg 9 (libass, QSV/VAAPI), `whisper-cli` (whisper.cpp Vulkan) con
`ggml-large-v3.bin` y VAD `ggml-silero-v5.1.2.bin`, `.venv` Python 3.14 con Pillow, numpy,
faster-whisper (modelo CT2 large-v3 en caché HF, 2.9 GB), rembg. Fuentes de marca en
`recursos/marca/fonts/` (libass) y `fonts-portada/` (PIL, variables). Identidad visual en
`recursos/marca/identidad.md`.
