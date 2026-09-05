#!/usr/bin/env python3
"""Claude Code Stop hook: the session closing ritual (CLAUDE.md).

When commits made since the session started touch working files (engine/, app/, tools/,
docs/superpowers/, CLAUDE.md, README.md, the core docs) and docs/JOURNAL.md or
docs/ROADMAP.md have not changed since the session started (committed or not), the stop
is blocked and the model is told what to update. Blocks at most three times per session
so a stuck situation ends with a warning to the user instead of a loop.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
WORK_PREFIXES = ("engine/", "app/", "tools/", "docs/superpowers/", "CLAUDE.md", "README.md",
                 "docs/CONTEXT.md", "docs/GLOSSARY.md", "docs/CURRENT-PIPELINE.md")
RITUAL_DOCS = ("docs/JOURNAL.md", "docs/ROADMAP.md")
MAX_BLOCKS = 3


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout
    return [line for line in out.splitlines() if line.strip()]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        payload = {}
    session = str(payload.get("session_id") or "unknown")
    state_file = ROOT / ".claude" / "hooks-state" / f"{session}.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    start_head = state.get("start_head") or (_git("rev-parse", "HEAD") or [""])[0]
    if not start_head:
        return 0

    committed = _git("diff", "--name-only", start_head, "HEAD")
    work = sorted(p for p in committed if p.startswith(WORK_PREFIXES))
    if not work:
        return 0

    changed_since_start = set(_git("diff", "--name-only", start_head))   # committed + working tree
    missing = [d for d in RITUAL_DOCS if d not in changed_since_start]
    if not missing:
        return 0

    blocks = int(state.get("stop_blocks", 0))
    if blocks >= MAX_BLOCKS:
        print(json.dumps({"systemMessage": f"Closing ritual skipped after {MAX_BLOCKS} reminders: "
                                            f"{', '.join(missing)} were not updated this session."}))
        return 0
    state.update({"start_head": start_head, "stop_blocks": blocks + 1})
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state), encoding="utf-8")

    sample = ", ".join(work[:6]) + (" ..." if len(work) > 6 else "")
    reason = (f"Session closing ritual (CLAUDE.md): commits in this session changed {len(work)} working "
              f"file(s) ({sample}) but {' and '.join(missing)} did not change. Before stopping: append "
              f"what happened to docs/JOURNAL.md, update the affected rows and 'Last update' in "
              f"docs/ROADMAP.md, save the memory pointer, and commit them.")
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
