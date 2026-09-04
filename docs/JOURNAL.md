# Journal: memory between sessions

> Live state of Lychnia. Updated every session. To resume: read this, then
> `CONTEXT.md` and the spec in progress.

## 2026-09-04: the repo is born; Engine spec written

Long session that started in the original repo (`multimedia-iglesia-tunja`) and ended by
opening this one.

- **Brainstorm** (skill `superpowers:brainstorming`, architectural path). Nine decisions
  closed by Andrés, table in `CONTEXT.md` §5: a mix of target machines, hybrid LLM with a local
  draft, Tauri + Python sidecar, scope up to delivery, separate model bundle, investigate
  the RVR1960 license, approach A (Python engine with a local API), Writer in chunks,
  Qwen3 4B by default.
- **Three spikes** (`docs/spikes/2026-09-03-feasibility.md`): (a) local LLM: one prompt with
  the whole sermon takes 100 min and degenerates; in 10 min chunks it works well in 15 min
  (4B) or 26 min (8B); (b) packaging with PyInstaller: 397 MB, runs standalone, wheels for
  the three operating systems exist; (c) RVR1960: bundling the complete text requires
  written permission from American Bible Society; copying verses per sermon is allowed.
- **Name:** first «Kerigma» (κήρυγμα); discarded the same day because of registered
  trademarks and a company in Colombia. After checking 22 candidates against companies,
  apps, GitHub, packages and domains, Andrés chose **Lychnia** (λυχνία, «lampstand»,
  Matthew 5:15): no collisions in any registry; its only cost is the pronunciation
  («lik-NEE-ah»). Repo at `~/Repositorios/amaujipe/lychnia`, published at
  https://github.com/amaujipe/lychnia (branch `main`). Pending: confirm by hand at sic.gov.co.
- **Engine spec** written: `docs/superpowers/specs/2026-09-04-engine-design.md`.
  Pending Andrés's review before moving to the implementation plan
  (skill `superpowers:writing-plans`).
- Bootstrap documentation: `README.md`, `CLAUDE.md`, `CONTEXT.md`, `CURRENT-PIPELINE.md`.
- **Language policy.** Andrés set the rule: Spanish between us, English for every artifact
  in the repo (code, docs, specs, commits); operator-facing text in Spanish through i18n.
  Added to the global Claude Code config (`~/.claude/CLAUDE.md`, mirrored in `dotfiles`),
  adapted from gentle-ai's output-style rule. The whole repo was translated the same day;
  file names changed to English (CONTEXT.md, CURRENT-PIPELINE.md, JOURNAL.md, feasibility
  spike, engine-design spec, ABS permission request) and the Engine spec adopted English
  identifiers plus an i18n section.

- **Engine spec approved** by Andrés (2026-09-04, after the English rewrite). Glossary saved
  as `docs/GLOSSARY.md`.

**Next step:** open Claude Code in this repo and run the `superpowers:writing-plans` skill on
`docs/superpowers/specs/2026-09-04-engine-design.md` to produce the implementation plan;
then implement, starting with the orchestrator and the golden tests.

**Pending outside code:**
- Send the email to licensing@americanbible.org (with a copy to contacto@sbcol.org); the
  English and Spanish draft is in `docs/abs-rvr1960-permission-request.md`, the data in
  square brackets is still missing.
- Confirm manually at sic.gov.co that «Lychnia» is not registered in Colombia (the official
  trademark registries could not be queried automatically).

**Done in the same session, afterwards:** fixtures of the 2026-08-30 sermon versioned in
`engine/tests/golden/fixtures/2026-08-30/` (TOMLs, SRT, TSV, silences, 87-shot plan and
expected `.ass`; 652 KB) with Andrés's authorization.
