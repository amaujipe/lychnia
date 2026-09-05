import threading
import time

from lychnia.orchestrator.events import EventBus
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.scheduler import Scheduler
from lychnia.orchestrator.status import State, derive_status
from lychnia.orchestrator.task import Gate, Resource, Task
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS, FAKE_TARGETS, MakeP, MakeX, MakeY, MakeZ, NeedsP


def _setup(make_project, tasks):
    project = Project(make_project(), artifacts=FAKE_ARTIFACTS)
    graph = TaskGraph(tasks, targets=FAKE_TARGETS)
    bus = EventBus()
    return project, graph, bus, bus.subscribe()


def test_chain_runs_in_order_and_stops_at_the_gate(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeY(), MakeZ()])
    project.artifact_path("given.txt").parent.mkdir(parents=True)
    project.artifact_path("given.txt").write_text("g", encoding="utf-8")
    report = Scheduler(graph, project, bus).run_target("all", wait=True)
    assert len(report.started) == 2
    assert project.artifact_path("x.txt").exists() and project.artifact_path("y.txt").exists()
    assert not project.artifact_path("z.txt").exists()
    assert [s.task for s in report.blocked] == ["make_z"] and report.blocked[0].state is State.BLOCKED
    types = [e.type for e in _drain(q)]
    assert types.index("task.finished") < len(types)
    assert types.count("task.started") == 2 and types.count("task.finished") == 2
    assert "artifact.changed" in types
    store = project.store
    assert store.get_artifact("x.txt").producer == "make_x"
    assert store.latest_run("make_y").status == "done" and store.latest_run("make_y").log_path
    assert derive_status(graph.tasks["make_y"], graph, project, store).state is State.AWAITING_APPROVAL


def test_after_approval_the_rest_runs(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeY(), MakeZ()])
    project.artifact_path("given.txt").parent.mkdir(parents=True)
    project.artifact_path("given.txt").write_text("g", encoding="utf-8")
    sched = Scheduler(graph, project, bus)
    sched.run_target("all", wait=True)
    project.store.approve("y.txt", project.artifact_hash("y.txt"), "andres")
    report = sched.run_target("all", wait=True)
    assert len(report.started) == 1 and report.blocked == []
    assert project.artifact_path("z.txt").exists()


def test_missing_provided_artifact_is_reported_not_run(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeY(), MakeZ()])
    report = Scheduler(graph, project, bus).run_target("all", wait=True)
    assert [s.task for s in report.blocked] == ["make_z"]
    assert report.blocked[0].missing == ["given.txt"]


def test_on_demand_task_runs_only_when_asked(make_project):
    project, graph, bus, q = _setup(make_project, [MakeX(), MakeP(), NeedsP()])
    sched = Scheduler(graph, project, bus)
    report = sched.run_target("needs_p", wait=True)
    assert not project.artifact_path("p.txt").exists()
    assert report.blocked[0].missing == ["p.txt"]
    report = sched.run_task("make_p", wait=True)
    assert project.artifact_path("p.txt").exists() and len(report.started) == 2   # make_x then make_p


class Slow(Task):
    name = "slow_a"
    inputs = ()
    outputs = ("x.txt",)
    resource = Resource.CPU_HEAVY
    gate = Gate.NONE
    running = 0
    peak = 0
    lock = threading.Lock()

    def fingerprint(self, cfg):
        return "s"

    def run(self, ctx):
        with Slow.lock:
            Slow.running += 1
            Slow.peak = max(Slow.peak, Slow.running)
        time.sleep(0.2)
        with Slow.lock:
            Slow.running -= 1
        ctx.output(self.outputs[0]).write_text("s", encoding="utf-8")


class SlowB(Slow):
    name = "slow_b"
    outputs = ("y.txt",)


def test_cpu_heavy_lane_runs_one_at_a_time(make_project):
    Slow.peak = 0
    project, graph, bus, q = _setup(make_project, [Slow(), SlowB()])
    graph.targets = {"both": ("slow_a", "slow_b")}
    Scheduler(graph, project, bus).run_target("both", wait=True)
    assert Slow.peak == 1


class Forever(Task):
    name = "forever"
    inputs = ()
    outputs = ("x.txt",)
    resource = Resource.LIGHT
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "f"

    def run(self, ctx):
        p = ctx.output("x.txt")
        p.write_text("partial", encoding="utf-8")
        while True:
            ctx.check_cancelled()
            time.sleep(0.02)


def test_cancel_terminates_and_cleans_partials(make_project):
    project, graph, bus, q = _setup(make_project, [Forever()])
    sched = Scheduler(graph, project, bus)
    report = sched.run_target("forever")
    deadline = time.time() + 5
    while not report.started and time.time() < deadline:
        time.sleep(0.01)
    assert sched.cancel(report.started[0])
    report.wait()
    assert project.store.get_run(report.started[0]).status == "cancelled"
    assert not project.artifact_path("x.txt").exists()
    assert not list(project.artifact_path("x.txt").parent.glob("*.partial"))
    assert any(e.type == "task.failed" and e.payload.get("reason") == "cancelled" for e in _drain(q))


class Boom(Task):
    name = "boom"
    inputs = ()
    outputs = ("x.txt",)
    resource = Resource.LIGHT
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "b"

    def run(self, ctx):
        ctx.log("about to fail")
        raise RuntimeError("kaput")


def test_failure_is_recorded_with_log(make_project):
    project, graph, bus, q = _setup(make_project, [Boom()])
    report = Scheduler(graph, project, bus).run_target("boom", wait=True)
    run = project.store.get_run(report.started[0])
    assert run.status == "failed" and "kaput" in run.error
    assert "about to fail" in (project.root / run.log_path).read_text(encoding="utf-8")
    assert derive_status(graph.tasks["boom"], graph, project, project.store).state is State.FAILED


def test_two_overlapping_targets_both_complete(make_project):
    project, graph, bus, q = _setup(make_project, [Slow(), SlowB()])
    graph.targets = {"a": ("slow_a",), "b": ("slow_b",)}
    sched = Scheduler(graph, project, bus)
    ra = sched.run_target("a")
    rb = sched.run_target("b")
    assert ra.wait(10) and rb.wait(10)
    assert project.artifact_path("x.txt").exists() and project.artifact_path("y.txt").exists()


def test_coordinator_exception_does_not_hang(make_project, monkeypatch):
    project, graph, bus, q = _setup(make_project, [MakeX()])
    sched = Scheduler(graph, project, bus)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("lychnia.orchestrator.scheduler.derive_status", _boom)
    report = sched.run_target("make_x", wait=True)
    assert report.wait(5)
    assert report.error is not None and "boom" in report.error
    assert report.started == []


def test_shutdown_cancels_active_runs(make_project):
    project, graph, bus, q = _setup(make_project, [Forever()])
    sched = Scheduler(graph, project, bus)
    report = sched.run_target("forever")
    deadline = time.time() + 5
    while not report.started and time.time() < deadline:
        time.sleep(0.01)
    assert report.started
    sched.shutdown()
    assert sched.active_runs() == []
    assert project.store.get_run(report.started[0]).status == "cancelled"


def test_launch_failure_marks_the_run_failed(make_project, monkeypatch):
    project, graph, bus, q = _setup(make_project, [MakeX()])
    sched = Scheduler(graph, project, bus)

    def _boom(*args, **kwargs):
        raise RuntimeError("fp boom")

    monkeypatch.setattr("lychnia.orchestrator.scheduler.full_fingerprint", _boom)
    report = sched.run_target("make_x", wait=True)
    assert report.wait(5)
    assert report.error is not None and "fp boom" in report.error
    assert project.store.latest_run("make_x").status == "failed"


def test_shutdown_stops_further_launches(make_project):
    project, graph, bus, q = _setup(make_project, [Slow(), SlowB()])
    graph.targets = {"both": ("slow_a", "slow_b")}
    sched = Scheduler(graph, project, bus)
    report = sched.run_target("both")
    deadline = time.time() + 5
    while not report.started and time.time() < deadline:
        time.sleep(0.01)
    assert report.started
    sched.shutdown()
    assert report.wait(10)
    assert sched.active_runs() == []


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out
