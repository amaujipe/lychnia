#!/usr/bin/env python3
"""Claude Code SessionStart hook.

1. Injects docs/ROADMAP.md into the model context so the forest view is always read.
2. Records the commit the session started from (`.claude/hooks-state/<session>.json`);
   the Stop hook compares against it to enforce the closing ritual.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        payload = {}
    session = str(payload.get("session_id") or "unknown")

    state_dir = ROOT / ".claude" / "hooks-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{session}.json"
    if not state_file.exists():                      # a resume keeps the original baseline
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout.strip()
        state_file.write_text(json.dumps({"start_head": head, "stop_blocks": 0}), encoding="utf-8")

    roadmap = ROOT / "docs" / "ROADMAP.md"
    if not roadmap.exists():
        return 0
    context = ("docs/ROADMAP.md, injected by the SessionStart hook. It is the living status board "
               "of the whole application: read it before anything else.\n\n"
               + roadmap.read_text(encoding="utf-8"))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": context}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
