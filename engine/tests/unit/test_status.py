import threading

from lychnia.orchestrator.context import Context
from lychnia.orchestrator.events import EventBus
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.status import State, derive_status, full_fingerprint, status_board
from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS, MakeP, MakeX, MakeY, MakeZ, NeedsP


def _setup(make_project, toml=None):
    root = make_project() if toml is None else make_project(toml)
    project = Project(root, artifacts=FAKE_ARTIFACTS)
    graph = TaskGraph([MakeX(), MakeY(), MakeZ(), MakeP(), NeedsP()])
    return project, graph, project.store


def _run(task, project, graph):
    """Execute a fake task the way the scheduler will: run, commit, register outputs."""
    run_id = project.store.start_run(task.name)
    ctx = Context(project, run_id, EventBus(), threading.Event())
    ctx.task_name = task.name
    task.run(ctx)
    ctx.commit()
    fp = full_fingerprint(task, project)
    for name in task.outputs:
        project.store.record_artifact(name, str(project.artifact_path(name)), project.artifact_hash(name), fp, task.name)
    project.store.finish_run(run_id, "done")


def test_missing_config_input_with_action(make_project):
    project, graph, store = _setup(make_project, "[meta]\nslug = \"p\"\n")
    st = derive_status(graph.tasks["make_x"], graph, project, store)
    assert st.state is State.MISSING_INPUT and st.missing == ["config:cut"]
    assert st.actions == [("action.fill_config", {"section": "cut"})]
    assert "cut" in st.message(lang="en")


def test_ready_then_done_then_stale(make_project):
    project, graph, store = _setup(make_project)
    x = graph.tasks["make_x"]
    assert derive_status(x, graph, project, store).state is State.READY
    _run(x, project, graph)
    assert derive_status(x, graph, project, store).state is State.DONE
    (project.root / "project.toml").write_text(
        (project.root / "project.toml").read_text().replace("end = 200.0", "end = 210.0"), encoding="utf-8")
    project.reload()
    st = derive_status(x, graph, project, store)
    assert st.state is State.STALE and st.actions == [("action.run_task", {"task": "make_x"})]


def test_missing_artifact_names_its_producer_and_provider(make_project):
    project, graph, store = _setup(make_project)
    st = derive_status(graph.tasks["make_z"], graph, project, store)
    assert st.state is State.MISSING_INPUT and st.missing == ["y.txt", "given.txt"]
    assert st.actions == [("action.run_task", {"task": "make_y"}), ("action.provide", {"artifact": "given.txt"})]
    st_p = derive_status(graph.tasks["needs_p"], graph, project, store)
    assert st_p.actions == [("action.run_task", {"task": "make_p"})]   # on-demand producer still suggested


def test_gate_flow(make_project):
    project, graph, store = _setup(make_project)
    _run(graph.tasks["make_x"], project, graph)
    y = graph.tasks["make_y"]
    _run(y, project, graph)
    st = derive_status(y, graph, project, store)
    assert st.state is State.AWAITING_APPROVAL and st.actions == [("action.approve", {"artifact": "y.txt"})]
    project.artifact_path("given.txt").write_text("g", encoding="utf-8")
    z = derive_status(graph.tasks["make_z"], graph, project, store)
    assert z.state is State.BLOCKED and z.blocked == ["y.txt"]
    store.approve("y.txt", project.artifact_hash("y.txt"), "andres")
    assert derive_status(y, graph, project, store).state is State.DONE
    assert derive_status(graph.tasks["make_z"], graph, project, store).state is State.READY
    # hand edit after approval: approval expires, artifact marked edited, downstream blocked again
    project.artifact_path("y.txt").write_text("y2", encoding="utf-8")
    assert derive_status(y, graph, project, store).state is State.APPROVAL_EXPIRED
    assert store.get_artifact("y.txt").edited is True
    assert derive_status(graph.tasks["make_z"], graph, project, store).state is State.BLOCKED


def test_upstream_change_expires_approval_without_deleting_anything(make_project):
    project, graph, store = _setup(make_project)
    _run(graph.tasks["make_x"], project, graph)
    _run(graph.tasks["make_y"], project, graph)
    store.approve("y.txt", project.artifact_hash("y.txt"), "andres")
    project.artifact_path("x.txt").write_text("x-changed", encoding="utf-8")
    st = derive_status(graph.tasks["make_y"], graph, project, store)
    assert st.state is State.APPROVAL_EXPIRED
    assert project.artifact_path("y.txt").exists()
    assert store.get_artifact("y.txt").approved_hash is not None


def test_unregistered_and_failed(make_project):
    project, graph, store = _setup(make_project)
    x = graph.tasks["make_x"]
    project.artifact_path("x.txt").parent.mkdir(parents=True)
    project.artifact_path("x.txt").write_text("old", encoding="utf-8")
    assert derive_status(x, graph, project, store).state is State.UNREGISTERED
    project.artifact_path("x.txt").unlink()
    run_id = store.start_run("make_x")
    store.finish_run(run_id, "failed", error="boom")
    st = derive_status(x, graph, project, store)
    assert st.state is State.FAILED and st.error == "boom"
    assert "boom" in st.message(lang="en")
    run_id = store.start_run("make_x")
    assert derive_status(x, graph, project, store).state is State.QUEUED
    store.set_run_status(run_id, "running")
    assert derive_status(x, graph, project, store).state is State.RUNNING


def test_board_lists_every_task_in_graph_order(make_project):
    project, graph, store = _setup(make_project)
    board = status_board(graph, project, store)
    assert [s.task for s in board] == ["make_x", "make_y", "make_z", "make_p", "needs_p"]
    assert board[0].state is State.READY
