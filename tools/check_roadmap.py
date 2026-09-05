#!/usr/bin/env python3
"""Consistency check for docs/ROADMAP.md, the living status board.

Fails (exit 1) when the roadmap is dead: a spec or plan exists that the roadmap does not
mention, the roadmap points to a file that does not exist, or its `Last update` date is
older than the newest commit that touched docs/superpowers/.

Used by the pre-commit guard hook, by the pytest suite and by hand:
    python3 tools/check_roadmap.py
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROADMAP = Path("docs/ROADMAP.md")
TRACKED_DIRS = (Path("docs/superpowers/specs"), Path("docs/superpowers/plans"))
LAST_UPDATE_RE = re.compile(r"\*\*Last update:\*\*\s*(\d{4}-\d{2}-\d{2})")
REFERENCE_RE = re.compile(r"superpowers/[\w./*-]+\.md")


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return ""


def check(root: Path) -> list[str]:
    root = Path(root)
    problems: list[str] = []
    roadmap_path = root / ROADMAP
    if not roadmap_path.exists():
        return [f"{ROADMAP} does not exist"]
    text = roadmap_path.read_text(encoding="utf-8")

    match = LAST_UPDATE_RE.search(text)
    if not match:
        problems.append(f"{ROADMAP}: missing '**Last update:** YYYY-MM-DD'")
        last_update = None
    else:
        last_update = dt.date.fromisoformat(match.group(1))
        if last_update > dt.date.today():
            problems.append(f"{ROADMAP}: Last update {last_update} is in the future")

    references = set(REFERENCE_RE.findall(text))

    # every spec and plan on disk is mentioned (exact path, or a glob such as engine-01-*.md)
    for folder in TRACKED_DIRS:
        for file in sorted((root / folder).glob("*.md")):
            rel = file.relative_to(root / "docs").as_posix()   # superpowers/plans/x.md
            if not any(fnmatch.fnmatch(rel, ref) for ref in references):
                problems.append(f"{ROADMAP} does not mention {file.relative_to(root).as_posix()}")

    # every exact reference in the roadmap exists
    for ref in sorted(references):
        if "*" in ref:
            if not list((root / "docs").glob(ref)):
                problems.append(f"{ROADMAP} references {ref} but nothing matches")
        elif not (root / "docs" / ref).exists():
            problems.append(f"{ROADMAP} references docs/{ref} but it does not exist")

    # the roadmap was touched at least as recently as the specs and plans
    if last_update is not None:
        newest = _git(root, "log", "-1", "--format=%cs", "--", "docs/superpowers")
        if newest and dt.date.fromisoformat(newest) > last_update:
            problems.append(f"{ROADMAP}: Last update {last_update} is older than the newest commit "
                            f"under docs/superpowers ({newest}); update the roadmap row and the date")
    return problems


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems = check(root)
    for p in problems:
        print(p)
    if not problems:
        print("ROADMAP.md is consistent")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
