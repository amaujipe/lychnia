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
- Enviar el correo a licensing@americanbible.org (con copia a contacto@sbcol.org); el
  borrador en inglés y español está en `docs/correo-abs-rvr1960.md`, faltan los datos entre
  corchetes.
- ~~Elegir el nombre definitivo~~ **Decidido: se queda Kerigma** (2026-09-04). Se verificaron
  diez alternativas (Candelero, Azotea, Amanuense, Pregonero, Ambón libres o casi; Pregón,
  Sermo, Escriba, Atrio, Lumbrera ocupados) y Andrés prefirió mantener Kerigma aunque
  existan apps y webs con ese nombre.

**Hecho en la misma sesión, después:** fixtures de la prédica 2026-08-30 versionadas en
`motor/tests/golden/fixtures/2026-08-30/` (TOMLs, SRT, TSV, silencios, plan de 87 planos y
`.ass` esperados; 652 KB) con autorización de Andrés.
