#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Bash: guard `git commit`.

Denies the commit when a spec or plan under docs/superpowers/ is about to be committed
without docs/ROADMAP.md, or when tools/check_roadmap.py finds the roadmap inconsistent.
Files named in a `git add ...` earlier in the same command line count as staged, because
the hook runs before any part of the command executes.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT / "tools"))
from check_roadmap import check  # noqa: E402

WATCHED_PREFIX = "docs/superpowers/"
ROADMAP = "docs/ROADMAP.md"


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout
    return [line for line in out.splitlines() if line.strip()]


def _changed_and_untracked() -> list[str]:
    status = _git("status", "--porcelain", "--untracked-files=all")
    return [line[3:] for line in status]


def _paths_from_git_add(command: str) -> set[str]:
    """Paths named in `git add ...` segments of the command (directories expanded)."""
    paths: set[str] = set()
    for segment in re.split(r"&&|\|\||;|\|", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        if len(tokens) >= 2 and tokens[0] == "git" and tokens[1] == "add":
            for tok in tokens[2:]:
                if tok.startswith("-"):
                    continue
                if (ROOT / tok).is_dir():
                    paths.update(p for p in _changed_and_untracked() if p.startswith(tok.rstrip("/") + "/"))
                else:
                    paths.add(tok)
    return paths


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    command = str(payload.get("tool_input", {}).get("command", ""))
    if not re.search(r"\bgit\b[^&|;]*\bcommit\b", command):
        return 0

    staged = set(_git("diff", "--cached", "--name-only"))
    staged |= _paths_from_git_add(command)
    if re.search(r"\bcommit\b[^&|;]*\s(-a|--all|-a[a-zA-Z]+)\b", command):
        staged |= set(_git("diff", "--name-only"))

    problems: list[str] = []
    touched_docs = sorted(p for p in staged if p.startswith(WATCHED_PREFIX))
    if touched_docs and ROADMAP not in staged:
        problems.append(f"{ROADMAP} is not part of this commit, but it changes: {', '.join(touched_docs)}. "
                        f"Update the matching row and 'Last update' in {ROADMAP} and add it to the commit.")
    if touched_docs or ROADMAP in staged:
        problems += check(ROOT)

    if problems:
        reason = "Commit blocked by tools/hooks/pre_commit_guard.py:\n- " + "\n- ".join(problems)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
