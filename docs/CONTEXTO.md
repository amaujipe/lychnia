# Contexto — de dónde viene Kerigma y qué tiene que hacer

> Escrito el 2026-09-04 al abrir este repo, a partir del pipeline que funciona hoy en
> `~/Repositorios/multimedia-iglesia-tunja` (en adelante «el repo original»). Este documento
> es suficiente para entender el dominio sin leer aquel repo; el detalle técnico del
> pipeline actual está en [PIPELINE-ACTUAL.md](PIPELINE-ACTUAL.md).

## 1. Quién y para qué

- **Andrés Jiménez** (amaujipe), desarrollador de software, sirve en el equipo multimedia
  de la Iglesia de Tunja (Colombia). No es editor de video de oficio.
- Cada domingo la iglesia graba la prédica y publica: video completo en YouTube, artículo
  en la web (Astro, repo `guia-clients/iglesia-de-tunja`, colección `blog`) y shorts entre
  semana. La Biblia que se usa y se proyecta es **Reina-Valera 1960**.
- Entre junio y septiembre de 2026 se construyó un pipeline con FFmpeg + Python + whisper,
  orquestado por `make`, donde **Claude Code hacía de director técnico**: redactaba guion,
  callouts, metadata y blog desde la transcripción, y corría los `make`.
- **Kerigma** convierte ese pipeline en una app de escritorio que corre sola, en cualquier
  PC de la iglesia o de un voluntario, con o sin internet, con o sin GPU.

## 2. Qué entra y qué sale

**Entra** (una carpeta `ENTREGA/` por prédica, producida por OBS en una sola sesión):

| Fuente | Qué es | Detalle |
|---|---|---|
| Maestro | Grabación principal de OBS (`.mkv`) | Su **audio** es el bueno (interfaz M-Audio vía REAPER). Su video es el programa conmutado; sirve de control de sincronía. |
| Cam A | Panorámica fija del salón (`.mkv`, Source Record) | 1080p30 CFR, muda (silencio digital). |
| Cam B | Cámara del pastor (`.mkv`, Source Record) | 1080p30 CFR, muda. Puede faltar. |
| Fotos | Del servicio, si hay | Portada con rostro y galería del blog. |
| `INFO.md` | Lo llena Andrés | Título, predicador, rol, pasaje, notas. Nombres propios verificados aquí. |

**Sale** (entregables de v1, «hasta la entrega»):

| Entregable | Hoy lo produce |
|---|---|
| `predica-final.mp4` 1080p30 multicámara A/B, versículos y frases quemados, audio normalizado | scripts |
| `predica-final.srt` recortado al corte | scripts |
| 4 a 5 shorts 9:16 con recorte al pastor y subtítulos | scripts |
| `miniatura.jpg` 1920×1080 (fondo IA + texto de marca) | scripts + fondo manual |
| Metadata de YouTube (títulos, descripción, capítulos, tags, comentario fijado) | Claude |
| Metadata de shorts (calendario, títulos, descripciones, hashtags) | Claude |
| Blog `.mdx` (Resumen / Enseñanza / Aplicación, componentes Astro) | Claude + scripts |
| Guion (`guion.md`) y callouts (`callouts.toml`) como intermedios aprobables | Claude |

Publicar (subir a YouTube, subir miniatura a R2 con `imageforge`, llevar el `.mdx` al repo
web) **queda fuera de v1** y sigue manual.

## 3. Cómo se produce hoy (resumen; detalle en PIPELINE-ACTUAL.md)

1. **Wave 0**: transcripción con faster-whisper (CPU int8, large-v3, VAD, sin contexto) →
   `predica.{srt,tsv,txt,vtt,json}`; auditoría de salud de cámaras (negros, congelados).
2. **Sincronía**: las cámaras vienen mudas; el offset se mide por cambios de diapositiva o
   energía de movimiento (`t_camara = t_maestro + off`, típico A −0.33, B −0.60). Se decide
   el **corte** (entrada/salida en segundos de maestro). Todo va a `proyecto.toml`.
3. **Gate A** (criterio humano): guion, **fases** del plan de cámaras → `planear_camaras.py`
   imanta cada corte al silencio real más largo y escribe `plan_camaras.json`; **callouts**
   en `callouts.toml` (versículos RVR1960, frases, puntos, listas, cada uno anclado a una
   frase real del SRT) → `gen_callouts.py` → `callouts.ass`. Frames de control para revisar.
4. **Carriles paralelos**: video (Fase 1 segmentos frame-exactos por GPU → clip de muestra)
   y contenido (miniatura, blog, subtítulos, metadata).
5. **Gate B**: revisar `muestra.mp4` (estilo, lip-sync, volumen).
6. **Entrega**: Fase 2 render final en software (concat + libass + cadena de voz), shorts,
   metadata de shorts.

Dos ideas de diseño que Kerigma hereda tal cual:

- **Una sola fuente de verdad por prédica**: `proyecto.toml` (meta, fuentes, sync, corte,
  video, audio, gate_b, shorts, plan.fases). Lo derivado no se configura. Los scripts son
  genéricos.
- **Parámetros ≠ artefactos aprobados**: el plan de planos y los callouts son archivos que
  un paso genera y una persona aprueba; nunca texto pegado en código.

## 4. Reglas duras (por qué existen)

| # | Regla | Qué pasó cuando no se cumplió |
|---|---|---|
| 1 | Render final en software (libx264); Fase 1 sí por GPU | VAAPI/QSV abortan al quemar subtítulos sobre un concat (2026-07-05) |
| 2 | Frame-exacto con `-frames:v round(dur·30)`, nunca `-t`; fronteras en la rejilla de 1/30 s | Cam B a 30.181 fps acumuló +2.2 s de desfase en 33 segmentos; 66 fronteras fuera de rejilla dieron −0.103 s de deriva (2026-08-23) |
| 3 | Un solo `.ass` con un único filtro libass | Overlays PNG encadenados: 3 h de render contra 10 min |
| 4 | Tiempos anclados a datos reales; si el ancla no existe, el generador muere | Callouts con tiempos de bosquejo salieron hasta 26 min fuera de lugar |
| 5 | Versículos: todos los que lee, completos, RVR1960 verificado en fuente, sin huecos en lectura corrida | Requisito explícito de Andrés; el pastor a veces se equivoca leyendo y se corrige |
| 6 | Fuentes por nombre interno (`Merriweather Light 18pt`, `DM Sans 9pt`); medir con PIL a `fs·K` (K = 0.573 / 0.757) | Paneles 1.7× más anchos que el texto |
| 7 | `aresample=48000` al final de la cadena de voz | loudnorm remuestrea a 192 kHz y el AAC quedaba a 96 kHz (2026-07-26) |
| 8 | Shorts: `-map 0:v -map 1:a` (audio del maestro), recorte al pastor que lo sigue, libx264 | QSV metía bloques verdes con filtros complejos; Andrés rechazó el blur-bg |
| 9 | Sincronía contra el audio que se usa en el render, mismo tipo de seek | Mezclar input-seek y output-seek da offsets falsos (2026-07-19) |
| 10 | Huellas por fase: un cambio de config no rehace lo caro | Agregar un short disparaba 20 min de Fase 1; una edición del TOML re-transcribió 90 min |

Otras constantes del estilo: cortes duros A/B, sin intro ni música; estética «Propuesta C»
(píldora dorada `#D4A843` para versículos, azul `#1C73A5` para frases; panel blanco
translúcido; Merriweather + DM Sans); portadas claras desde 2026-08-23; la portada **no**
repite el título del video (Pescaseo); cadena de voz canónica
`pan → highpass 80 → speechnorm → alimiter → loudnorm I=-15 → aresample 192k → alimiter → aresample 48k`
con tres perillas por prédica (mezcla, retardo, LUFS).

## 5. Decisiones tomadas para Kerigma (brainstorm 2026-09-03)

| # | Decisión | Alternativas descartadas |
|---|---|---|
| 1 | Equipos destino: **mezcla** (laptops modestas de voluntarios, el i9 + Iris Xe de Andrés, quizá un PC con NVIDIA). La app detecta capacidades y degrada. | Diseñar para una sola máquina |
| 2 | Textos sin internet: **borrador con LLM local**, y API (Claude) cuando haya internet. Híbrido automático. | Diferir textos; todo local siempre; plantillas sin LLM |
| 3 | Stack: **Tauri + UI web + sidecar Python**. El motor sigue en Python. | PySide6; Electron; servidor local + navegador |
| 4 | Alcance v1: **hasta la entrega**. Publicar sigue manual. | Hasta publicar; solo núcleo de video |
| 5 | Modelos: **instalador liviano + paquete de modelos aparte** (USB o descarga). La app funciona parcialmente sin ellos. | Instalador gigante; solo descarga |
| 6 | RVR1960: **pedir permiso a American Bible Society**; mientras, RVR1909 empaquetada + pegado manual del RVR1960 por versículo (flujo actual, permitido). | Empaquetar sin permiso; solo RVR1909 |
| 7 | Arquitectura: **enfoque A**: motor Python con orquestador propio y API local (127.0.0.1, token por sesión, sin CORS); Tauri es cáscara. | B: orquestar en Rust; C: stdio JSON-RPC |
| 8 | El Redactor local trabaja **por trozos de 10 min** (extracción JSON) + redacción corta; anclaje de tiempos siempre determinista; candidatos a shorts por heurística. | Un prompt con la transcripción entera (100 min y texto degradado) |
| 9 | Modelo local por defecto **Qwen3 4B** (Q4_K_M); 8B si hay GPU dedicada o el usuario acepta esperar. | Solo 8B |

Descomposición en sub-proyectos: **Motor → Proveedores de IA → Cáscara → Distribución**.
Cada uno con su spec y su plan.

## 6. Glosario

- **Maestro**: grabación principal de OBS; su audio es el de referencia y todos los tiempos
  «de maestro» se miden sobre él.
- **Offset** (`off_a`, `off_b`): `t_camara = t_maestro + off`. Negativo típico.
- **Corte** (`entrada`, `salida`): ventana del maestro que va al video final.
- **Tiempo de salida**: `t_maestro − entrada`. Los callouts se generan en tiempo maestro
  (`callouts.ass`) y se desplazan a tiempo de salida para el render (`callouts_render.ass`).
- **Gate A / Gate B**: los dos puntos de aprobación humana (plan + callouts; clip de muestra).
- **Fase 1 / Fase 2**: segmentos por plano (GPU) / composición final (software).
- **Huella**: cadena que resume la parte de la config que afecta a una fase; si no cambia, la
  fase no se rehace.
- **Callout**: rótulo quemado en el video: versículo (lower-third o pantalla completa),
  frase clave, punto del bosquejo o lista progresiva.
- **Aportado**: artefacto que no genera un script determinista sino una persona o el
  Redactor (guion, `callouts.toml`, fases, shorts, blog fuente, metadata, prompt del fondo).
