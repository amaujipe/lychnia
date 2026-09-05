import threading

import pytest

from lychnia.errors import Cancelled, TaskError
from lychnia.orchestrator.context import Context
from lychnia.orchestrator.events import EventBus
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS


def _ctx(make_project):
    project = Project(make_project(), artifacts=FAKE_ARTIFACTS)
    bus = EventBus()
    q = bus.subscribe()
    ctx = Context(project, run_id=7, bus=bus, cancel=threading.Event())
    ctx.task_name = "make_x"
    return ctx, q, project


def test_output_partial_then_commit(make_project):
    ctx, q, project = _ctx(make_project)
    partial = ctx.output("x.txt")
    assert partial.name == "x.txt.partial" and partial.parent.is_dir()
    partial.write_text("x", encoding="utf-8")
    final_paths = ctx.commit()
    assert final_paths == [project.artifact_path("x.txt")]
    assert project.artifact_path("x.txt").read_text(encoding="utf-8") == "x"
    assert not partial.exists()


def test_commit_without_writing_fails(make_project):
    ctx, q, project = _ctx(make_project)
    ctx.output("x.txt")
    with pytest.raises(TaskError) as exc:
        ctx.commit()
    assert exc.value.key == "task.output_missing" and exc.value.params["artifact"] == "x.txt"


def test_abort_removes_partials(make_project):
    ctx, q, project = _ctx(make_project)
    p = ctx.output("x.txt")
    p.write_text("half", encoding="utf-8")
    ctx.abort()
    assert not p.exists() and not project.artifact_path("x.txt").exists()


def test_log_and_progress_publish_events(make_project):
    ctx, q, project = _ctx(make_project)
    ctx.log("hello")
    ctx.progress(42.0, eta_s=10)
    e1, e2 = q.get_nowait(), q.get_nowait()
    assert e1.type == "task.log" and e1.payload == {"task": "make_x", "run": 7, "msg": "hello"}
    assert e2.type == "task.progress" and e2.payload == {"task": "make_x", "run": 7, "pct": 42.0, "eta_s": 10}
    assert ctx.log_lines == ["hello"]


def test_cancellation(make_project):
    ctx, q, project = _ctx(make_project)
    ctx.check_cancelled()
    ctx.cancel.set()
    with pytest.raises(Cancelled):
        ctx.check_cancelled()


def test_config_is_captured_at_start(make_project):
    ctx, q, project = _ctx(make_project)
    assert ctx.cfg.duration == 100.0
    (project.root / "project.toml").write_text(
        (project.root / "project.toml").read_text().replace("end = 200.0", "end = 300.0"), encoding="utf-8")
    project.reload()
    assert project.config.duration == 200.0 and ctx.cfg.duration == 100.0


def test_commit_rolls_back_when_a_rename_fails(make_project, monkeypatch):
    ctx, q, project = _ctx(make_project)
    p1 = ctx.output("x.txt")
    p2 = ctx.output("y.txt")
    p1.write_text("x", encoding="utf-8")
    p2.write_text("y", encoding="utf-8")

    from pathlib import Path
    original_replace = Path.replace
    call_count = [0]

    def replace_with_error(self, target):
        call_count[0] += 1
        if call_count[0] == 2:
            raise OSError("disk full")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", replace_with_error)

    with pytest.raises(TaskError) as exc:
        ctx.commit()

    assert exc.value.key == "task.commit_failed" and exc.value.params["artifact"] == "y.txt"
    assert not project.artifact_path("x.txt").exists()
    assert not project.artifact_path("y.txt").exists()
    partials = list((project.root / "work").glob("*.partial"))
    assert len(partials) == 0
