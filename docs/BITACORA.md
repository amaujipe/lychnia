# Bitácora — memoria entre sesiones

> Estado vivo de Kerigma. Se actualiza cada sesión. Para retomar: leer esto, luego
> `CONTEXTO.md` y la spec en curso.

## 2026-09-04 — Nace el repo; spec del Motor escrita

Sesión larga que empezó en el repo original (`multimedia-iglesia-tunja`) y terminó abriendo
este.

- **Brainstorm** (skill `superpowers:brainstorming`, camino arquitectural). Nueve decisiones
  cerradas por Andrés, tabla en `CONTEXTO.md` §5: mezcla de equipos, LLM híbrido con
  borrador local, Tauri + sidecar Python, alcance hasta la entrega, paquete de modelos
  aparte, investigar licencia RVR1960, enfoque A (motor Python con API local), Redactor por
  trozos, Qwen3 4B por defecto.
- **Tres spikes** (`docs/spikes/2026-09-03-viabilidad.md`): (a) LLM local: un prompt con la
  prédica entera tarda 100 min y degenera; por trozos de 10 min sale bien en 15 min (4B) o
  26 min (8B); (b) empaquetado con PyInstaller: 397 MB, corre standalone, ruedas para los
  tres SO existen; (c) RVR1960: empaquetar el texto completo requiere permiso escrito de
  American Bible Society; copiar versículos por prédica está permitido.
- **Nombre:** Kerigma (κήρυγμα, «proclamación»). Repo en `~/Repositorios/amaujipe/kerigma`.
- **Spec del Motor** escrita: `docs/superpowers/specs/2026-09-04-motor-design.md`.
  Pendiente de revisión de Andrés antes de pasar al plan de implementación
  (skill `superpowers:writing-plans`).
- Documentación de arranque: `README.md`, `CLAUDE.md`, `CONTEXTO.md`, `PIPELINE-ACTUAL.md`.

**Siguiente paso:** Andrés revisa la spec del Motor. Con su OK, `writing-plans` produce el
plan de implementación y se arranca por el orquestador con golden tests.

**Pendientes fuera de código:**
- Escribir a licensing@americanbible.org (con copia a contacto@sbcol.org) pidiendo permiso
  para copia offline de RVR1960 en una herramienta interna no comercial de la iglesia.
- Copiar al repo las fixtures de 2026-08-30 para los golden tests (dos TOML de ejemplo, el
  `predica.srt`, `plan_camaras.json` y `callouts.ass` de referencia). Los dos TOML ya están
  versionados en el repo original; el SRT y los artefactos viven en `proyectos/` (fuera de
  git allá): confirmar con Andrés que está bien versionarlos aquí como fixtures de prueba.
