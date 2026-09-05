"""docs/ROADMAP.md must mention every spec and plan and be at least as fresh as they are.

The logic lives in tools/check_roadmap.py so the pre-commit guard hook shares it.
"""
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_roadmap", REPO_ROOT / "tools" / "check_roadmap.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_roadmap_is_consistent():
    problems = _load_checker().check(REPO_ROOT)
    assert not problems, "\n".join(problems)
