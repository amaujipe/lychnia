# Spec — Motor de Lychnia (sub-proyecto 1)

**Fecha:** 2026-09-04 · **Estado:** borrador para revisión de Andrés
**Contexto previo:** [CONTEXTO.md](../../CONTEXTO.md) (decisiones), [PIPELINE-ACTUAL.md](../../PIPELINE-ACTUAL.md)
(lo que se migra), [spikes](../../spikes/2026-09-03-viabilidad.md) (viabilidad).

## 1. Qué es el Motor y qué no

El Motor es el proceso Python que hace todo el trabajo de Lychnia: sabe qué tareas existen,
en qué orden van, qué está hecho, qué falta y qué hay que aprobar; corre ffmpeg, whisper y
los generadores; y expone eso por una **API local** para la interfaz de escritorio y por
una **CLI** para operarlo sin interfaz. Reemplaza al `Makefile` del repo original y a Claude
Code como orquestador.

**Entra en este sub-proyecto:**

- Orquestador: grafo de tareas, huellas, estado persistente, gates, cola de ejecución con
  límites por recurso, progreso y cancelación.
- Migración de los scripts del pipeline a módulos genéricos sin estado global.
- API local (HTTP + WebSocket en `127.0.0.1`, token por sesión) y CLI equivalente.
- Configuración de proyecto (`proyecto.toml`) con lectura y edición que preserva comentarios.
- Detección de capacidades del equipo (encoders, GPU, RAM, modelos presentes, internet).
- Interfaces de los proveedores (Transcriptor, Redactor, Biblia, Detector) con la
  implementación **manual** de cada uno: el artefacto lo aporta una persona. La única
  implementación real incluida es el Transcriptor con faster-whisper, porque ya existe.
- Pruebas: unitarias, *golden* contra la prédica 2026-08-30 y de humo con medios locales.

**No entra** (sub-proyectos 2, 3 y 4): LLM local o por API, base bíblica, detección de
personas, interfaz Tauri, instaladores, paquete de modelos, publicación (YouTube, R2, repo web).

## 2. Principios que hereda

1. Una sola fuente de verdad por prédica: `proyecto.toml`. Lo derivado no se configura.
2. Parámetros ≠ artefactos aprobados. Lo aprobado (plan de planos, callouts) es un archivo
   que un paso genera, una persona aprueba y otro paso consume. Nunca se regenera a
   escondidas.
3. Los tiempos se anclan a datos reales. Si un ancla no existe, la tarea falla con un
   mensaje que dice cuál.
4. Un cambio de configuración no rehace lo caro: huellas por tarea.
5. Un solo código para los tres sistemas: `pathlib`, `subprocess` con listas, rutas con `/`
   para los filtros de ffmpeg, sin `os.chdir`, sin shell.
6. Las diez reglas duras de [CLAUDE.md](../../../CLAUDE.md) se cumplen en las tareas
   correspondientes y se verifican en pruebas.

## 3. Estructura del repo tras este sub-proyecto

```
lychnia/
├── motor/
│   ├── pyproject.toml               # paquete `lychnia`, Python 3.12
│   ├── lychnia/
│   │   ├── cli.py                   # `lychnia …` (Typer)
│   │   ├── api/                     # FastAPI: rutas, WebSocket, autenticación
│   │   ├── orq/                     # orquestador: grafo, tarea, huella, estado, cola, eventos
│   │   ├── proyecto/                # config (pydantic + tomlkit), descubrimiento de ENTREGA, capas
│   │   ├── tareas/                  # una clase por tarea del grafo (§5)
│   │   ├── media/                   # ffmpeg/ffprobe, encoders, cadena de voz, progreso, capacidades
│   │   ├── texto/                   # srt, anclaje, estilo ASS, callouts, subtítulos finales
│   │   ├── proveedores/             # interfaces + implementación manual + faster-whisper
│   │   └── recursos/                # fuentes de marca, plantilla de proyecto.toml, INFO.md
│   └── tests/
│       ├── unit/                    # sin ffmpeg ni medios
│       ├── golden/                  # fixtures de 2026-08-30: TOMLs, SRT, plan y .ass esperados
│       └── humo/                    # opt-in: medios reales acotados con LIMITE_MASTER
├── app/                             # reservado (sub-proyecto 3)
└── docs/
```

Los proyectos de prédicas viven **fuera del repo**, en una raíz que elige el operador
(por defecto `~/Lychnia/proyectos/`). Cada proyecto conserva la estructura actual
(`ENTREGA/`, `1-transcripcion/`, `3-guion/`, `4-video/`, `5-youtube/`, `6-blog/`,
`proyecto.toml`) para que las prédicas viejas sigan siendo legibles, y suma una carpeta
`.lychnia/` con el estado del orquestador.

## 4. Modelo de dominio

| Concepto | Qué es | Dónde vive |
|---|---|---|
| **Proyecto** | Una prédica: carpeta con `proyecto.toml` y `ENTREGA/`. Su id es el nombre de la carpeta (`AAAA-MM-DD_slug`). | disco |
| **Config** | El `proyecto.toml` validado y con derivados (`dur`, `nframes`, `fin_cam`, huellas). | memoria, se recarga al cambiar el archivo |
| **Tarea** | Nodo del grafo. Declara `nombre`, `entradas` (artefactos o secciones de config), `salidas` (artefactos), `huella(config)`, `recurso` (`gpu`, `cpu_pesado`, `liviano`), `gate` (si necesita aprobación humana para que sus consumidores corran) y `ejecutar(ctx)`. | código |
| **Artefacto** | Archivo producido por una tarea o **aportado** desde fuera. Se identifica por nombre lógico (`predica.srt`, `plan_camaras.json`) y se resuelve a una ruta dentro del proyecto. | disco + registro |
| **Registro** | Por artefacto: hash del contenido, huella con la que se produjo, quién lo produjo (tarea, humano, redactor), cuándo, y si está **aprobado** (con el hash aprobado). | `.lychnia/estado.sqlite` |
| **Corrida** | Una ejecución de una tarea: inicio, fin, resultado, log, progreso. | `.lychnia/estado.sqlite` + `.lychnia/logs/` |
| **Capacidades** | Lo que puede este equipo: encoders probados, GPU y su vendor, RAM, hilos, modelos presentes, internet. | memoria, se recalcula al arrancar y a pedido |

### 4.1 Estado de una tarea (derivado, no almacenado)

Se calcula al vuelo comparando registro, huellas y archivos en disco:

- `falta_entrada`: alguna entrada no existe (con la lista de qué falta y quién la produce).
- `lista`: todas las entradas existen y sus productores están aprobados si tienen gate.
- `hecha`: sus salidas existen, su huella coincide y el hash de las entradas no cambió.
- `desactualizada`: hecha, pero cambió una entrada o la huella.
- `corriendo` / `fallida` (con el error de la última corrida).
- `esperando_aprobacion`: hecha y con gate, pero nadie la aprobó.
- `aprobacion_caduca`: aprobada, pero cambió una entrada aguas arriba. **No se borra la
  aprobación ni se regenera**; se avisa.

El tablero (`lychnia estado`, `GET /proyectos/{id}/estado`) es la lista de tareas con su
estado y la acción sugerida, equivalente a `make estado` de hoy.

## 5. El grafo de tareas

Traducción del Makefile. Cada fila es una clase en `lychnia/tareas/`.

| Tarea | Entradas | Salidas | Huella | Recurso | Gate | Notas |
|---|---|---|---|---|---|---|
| `iniciar` | `ENTREGA/` | `proyecto.toml` | — | liviano | — | Descubre fuentes; rellena fecha y slug; no toca un TOML con fuentes ya puestas. |
| `transcribir` | `fuentes.maestro` | `predica.srt`, `.tsv`, `.txt`, `.vtt`, `.json` | hash del maestro | `cpu_pesado` (faster-whisper) o `gpu` (whisper-cli) | — | Un cambio de config **no** re-transcribe. Detector de bucle y respaldo. |
| `salud` | `fuentes.cam_a`, `fuentes.cam_b` | `_salud.txt` | hash de cámaras | liviano | — | Una por cámara, un reporte. |
| `plan` | `plan.fases`, `plan.cierre_a`, `corte`, `fuentes.maestro`, `audio.mezcla` | `plan_camaras.json`, `_sync/silencios.raw.txt` | fases + corte + mezcla | liviano | **Gate A** | Solo corre **a pedido** (nunca por dependencias). Cache de silencios por hash del maestro. |
| `callouts` | `callouts.toml` (aportado), `guion.md` (aportado), `predica.srt`, `huella_corte` | `callouts.ass`, `callouts_render.ass` | hash de callouts.toml + huella_corte | liviano | **Gate A** | Muere si un ancla no existe o hay solapes. |
| `frames_control` | `callouts.ass`, `plan_camaras.json`, cámaras, `sync` | `_gateA/hojas/*.jpg` | hash de .ass + plan | liviano | — | Material de revisión del Gate A. |
| `segmentos` | `plan_camaras.json` (aprobado), cámaras, `huella_video` | `_work/seg_*.mp4`, `segs.txt` | `huella_video` + hash del plan | **gpu** | — | Frame-exacto; valida plan, rejilla, fin de cámara; verifica suma de duraciones. |
| `muestra` | `segs.txt`, `callouts.ass`, `huella_audio`, `gate_b` | `_gateB/muestra.mp4` | huella_audio + gate_b + hash .ass | `cpu_pesado` | **Gate B** | Misma cadena de voz del render. |
| `render` | `segs.txt`, `callouts_render.ass`, `huella_audio`, muestra **aprobada** | `predica-final.mp4` | huella_audio + hash .ass + hash segs | **cpu_pesado** | — | libx264 siempre. Imprime y registra duración, frames, sample rate, LUFS, true peak. |
| `subtitulos` | `predica.srt`, `huella_corte` | `predica-final.srt` | huella_corte | liviano | — | |
| `shorts` | `shorts`, `shorts_overrides`, `fuentes.cam_b`, `predica.tsv`, `huella_audio` | `shorts/<id>.mp4` | por short: sus campos + huella_audio | `cpu_pesado` | — | Un short a la vez; no corre en paralelo con `render`. Rehace solo los shorts cuya huella cambió. |
| `miniatura` | `assets/fondo.png` (aportado), `meta.pasaje`, `miniatura.*` | `miniatura.jpg`, `miniatura-1280.jpg` | hash del fondo + campos | liviano | — | Nuevo bloque `[miniatura]` en el TOML: `fuerza` (texto o lista), `subtitulo`, `modo` (`claro|oscuro`), `con_rostro`, `fondo_ia`. |
| `blog` | `<slug>.src.mdx` (aportado), `publicacion.miniatura_url`, `publicacion.youtube_id` | `<slug>.mdx` | hash del src + campos | liviano | — | Resuelve `__MINIATURA_URL__` y `__YOUTUBE_ID__`. Los valores vienen del nuevo bloque `[publicacion]` del TOML (los escribe el operador al publicar; la URL de R2 es determinística). |

**Artefactos aportados** (no los produce ninguna tarea; los sube una persona por la API o
la CLI, y en el sub-proyecto 2 los producirá el Redactor por la misma API): `guion.md`,
`callouts.toml`, `assets/fondo.png`, `assets/prompt-fondo-miniatura.md`, `<slug>.src.mdx`,
`publicacion-youtube.md`, `shorts-metadata.md`. También son «aportadas» las secciones del
TOML que hoy escribe Claude: `sync`, `corte`, `plan.fases`, `shorts`, `miniatura`.

**Asistentes** (no son tareas del grafo; son comandos que devuelven números para que el
operador los escriba en el TOML): `sincronia.eventos_pantalla`, `sincronia.offset_pantalla`,
`sincronia.offset_movimiento`, `sincronia.escenas_maestro`, `medir.mezcla` (L−R en dB para
elegir `audio.mezcla`), `srt.buscar` (cues por rango o por texto, para elegir anclas).

### 5.1 Los dos gates

- **Gate A** cubre `plan` y `callouts`. `segmentos` no arranca sin `plan_camaras.json`
  aprobado; `muestra` no arranca sin `callouts.ass` aprobado.
- **Gate B** cubre `muestra`. `render` y `shorts` no arrancan sin la muestra aprobada.
- Aprobar = `POST …/artefactos/{nombre}/aprobar` guarda el hash aprobado. Si el archivo
  cambia después (se regenera el plan, se edita el TOML de callouts), el estado pasa a
  `aprobacion_caduca` y las tareas aguas abajo dejan de estar `lista`. Nunca se borra
  trabajo hecho.
- `plan_camaras.json` se puede **editar a mano** (hoy también); el Motor valida rejilla,
  huecos y planos cortos al leerlo y marca el artefacto como «editado» en el registro.

### 5.2 Modo de prueba

`LIMITE_MASTER=<seg>` (variable de entorno o campo de la petición `ejecutar`) acota corte,
plan, segmentos, render y subtítulos a los primeros N segundos de maestro, con la misma
semántica que hoy en `cfg.py`. Se registra en la huella para que una corrida acotada no se
confunda con una completa.

## 6. Orquestador

### 6.1 Huellas

Cada tarea implementa `huella(config) -> str`, una cadena determinista con los campos de
config que la afectan (ya definidos hoy: `huella_video`, `huella_audio`, `huella_corte`) más
los hashes de sus artefactos de entrada. Se guarda junto con cada salida producida. Una
tarea está `hecha` si sus salidas existen y la huella guardada es igual a la actual.

Hash de archivos grandes (medios): tamaño + mtime + hash de los primeros y últimos 8 MB.
Hash de archivos chicos (TOML, SRT, JSON, ASS): SHA-256 completo.

### 6.2 Estado

SQLite en `<proyecto>/.lychnia/estado.sqlite` (stdlib `sqlite3`, WAL). Tablas:
`artefactos` (nombre, ruta, hash, huella, productor, aprobado_hash, aprobado_por,
aprobado_en, editado), `corridas` (tarea, inicio, fin, estado, error, limite_master, log),
`eventos` (corrida, t, tipo, carga). Se puede borrar sin perder trabajo: el Motor lo
reconstruye desde el disco marcando todo como «sin registro» (equivalente a la primera
corrida de `make` sobre un proyecto viejo).

### 6.3 Cola y recursos

Un planificador con tres carriles y capacidad `gpu=1`, `cpu_pesado=1`, `liviano=4`. Al
pedir «ejecutar hasta X» (por ejemplo `entrega`), el orquestador resuelve el cierre
transitivo, descarta lo `hecho`, se detiene en el primer gate no aprobado o artefacto
aportado que falte, y encola lo `listo` respetando recursos. Los dos carriles (video y
contenido) corren solos en paralelo porque no comparten recursos.

Objetivos compuestos (equivalentes a los targets de hoy): `preparar` (transcribir + salud),
`gate_a` (callouts + frames_control), `video` (segmentos + muestra), `contenido`
(subtitulos + miniatura + blog), `entrega` (render + shorts).

### 6.4 Ejecución de una tarea

Cada tarea recibe un `Contexto` con la config, las rutas resueltas, las capacidades, el
límite de prueba, un `log(msg)` y un `progreso(pct, eta_s)`. Escribe sus salidas en
`<salida>.parcial` y las renombra al terminar (equivalente a `.DELETE_ON_ERROR`). ffmpeg se
lanza con `-progress pipe:1` y `-nostats`; el Motor parsea `out_time_us` para el progreso.
Cancelar = terminar el subproceso (SIGTERM, luego SIGKILL a los 5 s) y borrar los `.parcial`.

### 6.5 Eventos

Todo lo que pasa se publica como evento en memoria y por WebSocket: `tarea.inicio`,
`tarea.progreso`, `tarea.log`, `tarea.fin`, `tarea.error`, `artefacto.cambio`,
`aprobacion.cambio`, `config.cambio`. La CLI los imprime; la UI los pinta.

## 7. API local y CLI

### 7.1 Transporte y seguridad

- FastAPI + uvicorn en `127.0.0.1`, puerto aleatorio libre.
- Al arrancar, el Motor imprime en stdout una única línea JSON `{"puerto": …, "token": …}`
  y la escribe en `<datos>/motor.json` con permisos 0600 (Tauri lee stdout; la CLI lee el
  archivo). El token se genera por sesión (`secrets.token_urlsafe(32)`).
- Toda ruta exige `Authorization: Bearer <token>`; sin él, 401. Sin CORS. Rechazo explícito
  de peticiones con cabecera `Origin` (evita el ataque desde una página web abierta).
- Un solo Motor por usuario: si `motor.json` apunta a un proceso vivo que responde, la CLI
  lo usa; si no, arranca uno.

### 7.2 Rutas

```
GET  /sistema/capacidades                 encoders, gpu, ram, hilos, modelos, internet, versiones
GET  /proyectos                           lista (raíz configurable)
POST /proyectos                           {fecha, slug} → crea carpeta desde plantilla; o {ruta} → adopta una existente
GET  /proyectos/{id}                      resumen (meta, fuentes, corte, dur…)
GET  /proyectos/{id}/config               TOML como JSON tipado + texto crudo
PUT  /proyectos/{id}/config               parche por secciones; preserva comentarios (tomlkit); valida
GET  /proyectos/{id}/estado               tablero: tareas con estado y acción sugerida
POST /proyectos/{id}/ejecutar             {objetivo | tarea, limite_master?} → ids de corridas
POST /proyectos/{id}/cancelar             {corrida}
GET  /proyectos/{id}/artefactos           registro completo
GET  /proyectos/{id}/artefactos/{nombre}  descarga (texto o binario) con ETag = hash
PUT  /proyectos/{id}/artefactos/{nombre}  aportar (solo nombres declarados como aportables)
POST /proyectos/{id}/artefactos/{nombre}/aprobar     {hash, quien}
DELETE /proyectos/{id}/artefactos/{nombre}/aprobar
POST /proyectos/{id}/asistentes/{nombre}  sincronía, medir mezcla, buscar en el SRT
GET  /proyectos/{id}/corridas/{corrida}/log
WS   /eventos?proyecto=…                  flujo de eventos (§6.5)
```

### 7.3 CLI

Espejo de la API con Typer, en español, misma semántica que los targets de hoy:

```
lychnia servir                              # arranca el Motor (lo usa Tauri)
lychnia capacidades
lychnia nuevo 2026-09-06 titulo-corto       # crea el proyecto desde la plantilla
lychnia estado  [-p <proyecto>]
lychnia config  [-p …] [seccion.campo valor]
lychnia ejecutar preparar|plan|gate_a|video|contenido|entrega|<tarea> [-p …] [--limite 700]
lychnia aportar callouts.toml ruta/al/archivo
lychnia aprobar plan_camaras.json | callouts.ass | muestra.mp4
lychnia asistente sincronia.offset_pantalla --ref … --test … --crop … --t 96
lychnia log <corrida> [--seguir]
```

`-p` toma la carpeta actual si es un proyecto. La CLI sin Motor corriendo lo arranca en
segundo plano y lo apaga al salir si ella lo arrancó.

## 8. Configuración

### 8.1 `proyecto.toml`

Los bloques actuales (§2 de PIPELINE-ACTUAL) más dos nuevos:

```toml
[miniatura]
fuerza    = "LÓGICO O BÍBLICO"      # o lista de líneas
subtitulo = "Noé esperó la voz, no la evidencia"
modo      = "claro"                  # claro | oscuro
con_rostro = false
fondo_ia  = true

[publicacion]                        # lo escribe el operador al publicar (fuera de v1 el subir)
miniatura_url = ""                   # determinística: https://media.iglesiadetunja.org/predicas/<fecha>/<slug>/miniatura.jpg
youtube_id    = ""
```

Modelo pydantic con validación (rangos, `salida > entrada`, `delay ≥ 0`, mezcla en las tres
opciones, fases contiguas y alineadas al corte, shorts con campos completos). Lectura con
`tomllib`; edición con `tomlkit` para preservar comentarios (la plantilla comentada es
documentación para el operador). Derivados como hoy.

### 8.2 Configuración del Motor (por usuario)

`<datos>/config.toml` (ruta por `platformdirs`: `~/.local/share/lychnia` en Linux,
`%LOCALAPPDATA%\lychnia` en Windows, `~/Library/Application Support/lychnia` en macOS):
raíz de proyectos, carpeta de modelos, encoder forzado (`HW_ENCODER`), hilos, transcriptor
preferido, ruta a ffmpeg si no está en PATH.

### 8.3 Capacidades

Al arrancar y a pedido: `ffmpeg -encoders` + prueba real de 1 frame por encoder
(h264_qsv, h264_nvenc, h264_amf, h264_videotoolbox, libx264); vendor de GPU (Vulkan si
hay `vulkaninfo`, si no por `lspci`/`wmic`/`system_profiler`); RAM y hilos; modelos
presentes en la carpeta de modelos con su manifiesto; internet (HEAD a un host conocido
con timeout de 2 s). El resultado alimenta la elección de encoder de `segmentos` y, en el
sub-proyecto 2, la elección de modelo del Redactor.

## 9. Migración de los scripts

Reglas para pasar cada script de `recursos/scripts/pipeline/` a un módulo de `lychnia`:

1. Sin estado global al importar: fuera `CFG = Config(...)`, `CUES = parse()`, `_find_fonts()`
   subiendo directorios. Todo entra por parámetros (`config`, `rutas`, `fuentes`).
2. Sin `os.chdir` ni `sys.path.insert`. Las rutas para filtros de ffmpeg pasan por una
   función `ruta_filtro(p)` que devuelve una ruta escapada válida en los tres sistemas
   (hoy se resuelve con `relpath` desde la raíz del repo; en Lychnia no hay raíz del repo
   en tiempo de ejecución).
3. Sin `print` como salida: `ctx.log()` y valores de retorno tipados.
4. Sin `sys.exit` ni `assert`: excepciones `ErrorDeValidacion(campo, mensaje, sugerencia)`
   y `ErrorDeTarea(mensaje)`.
5. La lógica no cambia. La garantía es el *golden test*: con las fixtures de 2026-08-30 el
   plan debe dar los mismos 87 planos y `gen_callouts` el mismo `.ass` byte a byte.
6. `generar_miniatura` deja de ser un script por prédica: textos desde `[miniatura]`.
7. Las fuentes de marca (`fonts/` para libass, `fonts-portada/` para PIL) y la plantilla de
   `proyecto.toml` e `INFO.md` viajan dentro del paquete (`lychnia/recursos/`).

Mapa script → módulo: `cfg.py` → `proyecto/config.py`; `srt_util.py` → `texto/srt.py`;
`estilo_callouts.py` → `texto/estilo_ass.py`; `gen_callouts.py` → `tareas/callouts.py` +
`texto/callouts.py`; `planear_camaras.py` → `tareas/plan.py`; `armar_segmentos.py` →
`tareas/segmentos.py` + `media/encoders.py`; `render_final.py` → `tareas/render.py`;
`clip_muestra.py` → `tareas/muestra.py`; `hacer_srt.py` → `tareas/subtitulos.py`;
`armar_shorts.py` + `rastrear.py` → `tareas/shorts.py` + `media/rastreo.py`;
`frames_control.py` → `tareas/frames_control.py`; `transcribir.py` →
`proveedores/transcriptor_fasterwhisper.py` + `tareas/transcribir.py`; scripts de sincronía
→ `media/sincronia.py` (asistentes); `salud_camaras.py` → `tareas/salud.py`;
`generar_miniatura` → `tareas/miniatura.py`.

## 10. Proveedores (interfaces; implementación en el sub-proyecto 2)

```python
class Transcriptor(Protocol):
    def transcribir(self, audio: Path, salida: Path, prefijo: str, ctx) -> list[Cue]: ...

class Redactor(Protocol):
    def extraer(self, trozo: Trozo, ctx) -> ExtractoTrozo: ...          # 10 min → JSON
    def redactar(self, extractos: list[ExtractoTrozo], pedido: Pedido, ctx) -> str: ...

class Biblia(Protocol):
    def versiculo(self, ref: Referencia) -> str | None: ...               # None = no disponible
    def version(self) -> str: ...

class Detector(Protocol):
    def posicion_horizontal(self, video: Path, ini: float, fin: float, ctx) -> list[Nodo]: ...
```

En este sub-proyecto: `TranscriptorFasterWhisper` (real), `RedactorManual` (devuelve
«artefacto aportado por el operador»: la tarea queda en `falta_entrada` con instrucción),
`BibliaManual` (siempre `None`: el operador pega el texto en `callouts.toml`, como hoy) y
`DetectorMediana` (el algoritmo actual de `rastrear.py`). La elección del proveedor por
capacidades e internet llega con el sub-proyecto 2.

## 11. Errores

- Cada error de validación nombra el campo del TOML, qué está mal y qué hacer
  (`sync.audio_delay_ms debe ser ≥ 0; para adelantar el audio, corregí los offsets`).
- Cada error de tarea guarda el comando de ffmpeg que falló y las últimas 50 líneas de su
  stderr en el log de la corrida.
- Falta de un aportado: estado `falta_entrada` con texto de instrucción, igual que los
  mensajes `⚠ Falta …` del Makefile de hoy.
- Falta de herramienta (ffmpeg, modelo): error al arrancar la tarea, no a mitad; las
  capacidades ya lo saben antes.
- Ninguna salida parcial queda con su nombre final.

## 12. Pruebas

| Nivel | Qué | Cómo |
|---|---|---|
| Unitarias | Grafo, estados derivados, huellas, gates, cola por recursos, parseo de progreso de ffmpeg, validación de config, `ruta_filtro` en los tres SO (con `pathlib.PureWindowsPath`) | pytest, sin medios |
| Golden | `plan` → 87 planos idénticos; `callouts` → `.ass` byte a byte; `subtitulos` → `.srt` esperado; `config` sobre el `proyecto.EJEMPLO-2026-08-30.toml` | fixtures copiadas del repo original: los dos TOML de ejemplo, `predica.srt` de 2026-08-30, `plan_camaras.json` y `callouts.ass` de referencia |
| API | 401 sin token, 200 con token, rechazo de `Origin`, ciclo completo aportar → aprobar → estado | `TestClient` |
| Humo (opt-in) | `ejecutar entrega --limite 700` sobre los medios de `prueba-render`: frame-exacto (142.5 s = 4275 f), 48 kHz mono, LUFS y true peak dentro de rango, un short 1080×1920 | marcador `@pytest.mark.medios`, ruta por variable de entorno |
| Portabilidad | El paquete importa y la API arranca en Windows y macOS | CI con matriz (sub-proyecto 4 la completa; aquí queda el workflow mínimo) |

## 13. Fuera de alcance y siguientes pasos

- **Sub-proyecto 2** (Proveedores de IA): `RedactorLocal` (llama-server + Qwen3 por trozos),
  `RedactorAPI` (Claude), `BibliaSQLite` (RVR1909 empaquetada; RVR1960 si llega el permiso),
  `DetectorPersona`, selección por capacidades. Todos entran por las interfaces de §10 y
  aportan artefactos por la API de §7.
- **Sub-proyecto 3** (Cáscara): Tauri arranca el Motor como sidecar, lee la línea JSON de
  stdout, y la UI consume §7. Pantallas de Gate A (plan + callouts + frames de control) y
  Gate B (muestra).
- **Sub-proyecto 4** (Distribución): PyInstaller por SO en CI, `llama-server` como binario
  aparte, paquete de modelos con manifiesto, importación desde USB, instaladores Tauri.

## 14. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Migrar 20 scripts introduce regresiones sutiles de tiempo | Golden tests byte a byte antes de tocar lógica; migrar uno por uno |
| Rutas y filtros de ffmpeg en Windows (`C:\`, `:` en `subtitles=`) | `ruta_filtro` con pruebas unitarias por SO; ya resuelto una vez en el repo original (docs 17 §4.6) |
| Un proyecto viejo sin `.lychnia/` ni registro | Reconstrucción desde disco; estado «sin registro» hasta la primera corrida |
| SQLite bloqueado por dos procesos | Un solo Motor por usuario (§7.1); WAL |
| El operador edita `proyecto.toml` mientras corre una tarea | La tarea trabaja con la config capturada al arrancar; el cambio dispara `desactualizada` al terminar |
