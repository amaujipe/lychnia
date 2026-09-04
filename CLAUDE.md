# Lychnia — instrucciones para Claude Code

## Qué es esto

App de escritorio multiplataforma que reemplaza al pipeline de prédicas de
`~/Repositorios/multimedia-iglesia-tunja` (Make + scripts + Claude Code como orquestador)
por un motor propio con API local y una UI Tauri. Ver `README.md`.

## Lee esto al empezar una sesión

1. `docs/BITACORA.md`: qué se hizo la última vez y qué sigue.
2. `docs/CONTEXTO.md`: origen, entregables, reglas duras, decisiones tomadas.
3. La spec del sub-proyecto en curso en `docs/superpowers/specs/`.
4. Si hace falta el detalle del pipeline actual: `docs/PIPELINE-ACTUAL.md` y el código fuente
   en `~/Repositorios/multimedia-iglesia-tunja/recursos/scripts/pipeline/` (versionado).

La memoria Engram del proyecto anterior está bajo el nombre `multimedia-iglesia-tunja`;
buscar ahí con `all_projects=true` si falta contexto de decisiones de junio a septiembre 2026.

## Cómo trabaja Andrés

- Debate punto por punto antes de construir: opciones numeradas, una línea de
  recomendación cada una. Decide él. Luego se implementa de punta a punta y se prueba
  antes de reportar.
- Explicaciones cortas. Si pide «explícamelo más pero sin tanto texto», 5 a 8 líneas.
- Español de Colombia. En mensajes de la herramienta al operador se usa voseo suave
  («revisá», «aprobalo»), heredado del Makefile original.
- Nunca proponer versionar los textos de las prédicas producidas (decisión cerrada).

## Reglas duras del dominio (no negociables, aprendidas a los golpes)

Están explicadas en `docs/CONTEXTO.md` §4. Las diez en una línea cada una:

1. Render final en software (libx264); solo la Fase 1 (segmentos) va por GPU.
2. Frame-exacto (`-frames:v`) y fronteras de plano en la rejilla de 1/30 s.
3. Un solo `.ass` quemado con un único filtro libass.
4. Cada tiempo se ancla a datos reales (SRT, silencios); el LLM nunca inventa tiempos.
5. Versículos: todos los que lee, completos, RVR1960 verificado, sin huecos en lectura corrida.
6. Fuentes por nombre interno y calibración libass/PIL (Merriweather 0.573, DM Sans 0.757).
7. `aresample=48000` al final de la cadena de audio.
8. Shorts con audio del maestro y recorte al pastor a pantalla completa, nunca blur.
9. Sincronía medida contra el audio del render, con el mismo tipo de seek.
10. Un cambio de config no rehace lo caro: huellas por fase.

## Convenciones de código

- Python 3.12 (objetivo de empaquetado con PyInstaller), `pathlib`, `subprocess` con listas
  (nunca shell), rutas con `/` para filtros de ffmpeg. Un solo código para los tres SO.
- Nombres en español en dominio y CLI (tareas, artefactos, gates); inglés solo donde la
  librería lo impone.
- Tests: unitarios para orquestador y huellas; *golden tests* contra los artefactos reales
  de la prédica 2026-08-30 (plan de 87 planos y `callouts.ass` byte a byte).
- Commits en español, estilo `feat(motor): …`, `docs: …`.
