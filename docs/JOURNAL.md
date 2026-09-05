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

## 2026-09-04 (later): Engine implementation plan 01 written

- Ran `superpowers:writing-plans` on the Engine spec. The spec is too large for a single
  plan with concrete steps, so the Engine is split into **four plans**, each leaving the
  suite green: 01 Foundation, 02 Text lane (golden tests: 87 shots, `callouts.ass`,
  `final.srt`), 03 Media lane (ffmpeg tasks, smoke tests), 04 API + CLI.
- **Plan 01 written:** `docs/superpowers/plans/2026-09-04-engine-01-foundation.md`
  (15 tasks, TDD, ~80 unit tests, one golden config test). It covers package skeleton
  (mise pin 3.12.14, venv + pip, hatchling), errors + i18n catalogs, frame grid and voice
  chain, `project.toml` model with derived values and fingerprints, legacy adapter for the
  Spanish fixtures, comment-preserving edits (tomlkit), hashing, layout/discovery/template,
  SQLite store, artifact registry + task graph + Project, event bus + context, derived
  statuses, three-lane scheduler, ffmpeg runner + `filter_path`, i18n static scan.
- Decisions taken while planning, pending Andrés's confirmation (listed at the top of the
  plan): four plans; two extra states `blocked` and `unregistered`; input prefixes
  `source:` / `config:`; logical names `blog.src.mdx`, `blog.mdx`, `control_sheets.txt`,
  `shorts.txt`; `[cut]` optional so a fresh project loads; golden comparisons normalize
  CRLF (the fixtures were written on Windows); thread-based runner; quoted `filter_path`.
- Environment facts: no `uv`/`poetry` on the machine; Python 3.12.14 installed via mise but
  not pinned; ffmpeg 9.0.1; no numpy/Pillow/tomlkit outside a venv yet.

- **`docs/ROADMAP.md` created** at Andrés's request: a living status board of the four
  sub-projects (Engine, AI providers, Shell, Distribution), the state of every spec and plan,
  what is still undesigned and the pending work outside the code. `CLAUDE.md` now lists it as
  reading number 1 and fixes the closing ritual: JOURNAL + ROADMAP + memory.

- **Plan 01 decisions confirmed** by Andrés (the eight listed at the top of the plan).
- **Enforcement of the documentation ritual** (Andrés asked how to guarantee it, given that
  instructions alone are probabilistic): `tools/check_roadmap.py` + pytest test, and three
  Claude Code hooks in `.claude/settings.json` (`SessionStart` injects the ROADMAP,
  `PreToolUse` guards `git commit`, `Stop` blocks the turn until JOURNAL and ROADMAP change
  after commits that touched working files). A git `pre-commit` hook for commits made
  outside Claude Code was deferred by Andrés. Details in `ROADMAP.md` §5.

**Next step:** execute plan 01 (`superpowers:subagent-driven-development`, Andrés still has to
pick subagents or inline), then write plan 02.

## 2026-09-04: Engine plan 01 executed

Executed with `superpowers:subagent-driven-development`: 15 tasks, every task reviewed,
eight fix rounds in total (Tasks 6, 8, 9, 10, 11, 13 ×2, 14). What landed, one line per
task group:

- Package skeleton (Python 3.12 pin, hatchling, pytest harness), error types and the
  es/en i18n message catalogs.
- `project.toml` model with derived values and fingerprints, the legacy adapter for the
  2026-08-30 fixtures, and comment-preserving config edits (tomlkit).
- Content hashing (fast path for large media), project layout, source discovery and the
  localized `project.toml` template.
- SQLite state store (artifacts, runs, events) and the artifact registry, task graph with
  composite targets, and the `Project` object.
- Event bus and task context (partial outputs, cancellation), derived task statuses and
  gates, and the three-lane scheduler (gpu/cpu_heavy/light).
- ffmpeg runner with progress, cancellation and `filter_path` escaping.
- i18n static scan (this task): a test that fails when code uses a message key missing
  from either catalog, when a dynamic `status.*` key for a `State` is missing, or when
  Spanish operator text is inlined instead of routed through the catalogs.

**Suite: 104 tests passing** (101 before this task, plus the 3 new scan tests).

Deviations and decisions taken during execution (each affects how the code reads, not the
plan's scope):

- `pyproject.toml` has no `readme` field: hatchling cannot reference `../README.md` from
  inside `engine/`.
- `patch_config` rejects array-of-tables sections and nested values with `ConfigError`
  (i18n keys `validation.unsupported_patch_section` / `validation.unsupported_patch_value`).
- The `project.toml` template renders its example values through i18n
  (`template.example_*` keys) instead of hardcoding Spanish strings.
- `StateStore` fetches rows inside its own lock (`_query`/`_execute`) so concurrent threads
  cannot race, and it gained `set_run_log`.
- `Context.commit()` rolls back a multi-output commit when a rename fails
  (`task.commit_failed`).
- The scheduler uses one completion queue per coordinator, guards the coordinator loop
  (`RunReport.error`, a `scheduler.failed` event), locks `_active`, captures the fingerprint
  and output paths before `task.run`, fails the run if launch setup itself raises, and stops
  new launches once `shutdown()` is called.
- `Project.config` and `Project.store` lazy loads are locked.
- `run_ffmpeg` terminates the child process and closes its pipes in a `finally` block.
- The fake task `NeedsP` (test fixture) produces `np.txt`.
- The two type-narrowing `assert`s in the ffmpeg runner became an explicit guard clause.
- The i18n scan also caught five event-type strings (`task.started`, `task.progress`,
  `task.log`, `task.finished`, `task.failed`) that share the `task.*` namespace with the
  error keys; added to both catalogs with operator-facing text.

Deferred minors are tracked in the SDD ledger under
`.superpowers/sdd/2026-09-04-engine-01-foundation/` and will be triaged by the final
whole-branch review.

**Next step:** write plan 02 (text lane) with `superpowers:writing-plans`, then execute it.
