"""Task status derived on the fly from disk, registry and fingerprints (spec §4.1)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from lychnia.i18n import t
from lychnia.orchestrator.artifacts import CONFIG_PREFIX, SOURCE_PREFIX, is_config, is_source
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.state import StateStore
from lychnia.orchestrator.task import Gate, Task
from lychnia.project.project import Project


class State(str, Enum):
    MISSING_INPUT = "missing_input"
    BLOCKED = "blocked"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    STALE = "stale"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVAL_EXPIRED = "approval_expired"
    UNREGISTERED = "unregistered"


RUNNABLE = {State.READY, State.STALE, State.FAILED, State.UNREGISTERED}


@dataclass
class TaskStatus:
    task: str
    state: State
    missing: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    error: str | None = None
    actions: list[tuple[str, dict]] = field(default_factory=list)

    def message(self, lang: str | None = None) -> str:
        key = f"status.{self.state.value}"
        if self.state is State.MISSING_INPUT:
            return t(key, lang, items=", ".join(self.missing))
        if self.state is State.BLOCKED:
            return t(key, lang, items=", ".join(self.blocked))
        if self.state is State.FAILED:
            return t(key, lang, error=self.error or "")
        return t(key, lang)

    def action_texts(self, lang: str | None = None) -> list[str]:
        return [t(key, lang, **params) for key, params in self.actions]


def full_fingerprint(task: Task, project: Project) -> str:
    """Task fingerprint plus the hashes of its artifact and source inputs."""
    parts = [task.fingerprint(project.config), f"limit={project.master_limit}"]
    parts += [f"{name}={project.input_hash(name)}" for name in task.inputs if not is_config(name)]
    return "|".join(parts)


def suggest_actions(task: Task, graph: TaskGraph, project: Project, status: TaskStatus) -> list[tuple[str, dict]]:
    actions: list[tuple[str, dict]] = []
    if status.state is State.MISSING_INPUT:
        for name in status.missing:
            if is_config(name):
                actions.append(("action.fill_config", {"section": name[len(CONFIG_PREFIX):].split(".")[0]}))
            elif is_source(name):
                actions.append(("action.add_source", {"source": name[len(SOURCE_PREFIX):]}))
            elif (producer := graph.producer_of(name)) is not None:
                actions.append(("action.run_task", {"task": producer.name}))
            elif project.artifact_spec(name).providable:
                actions.append(("action.provide", {"artifact": name}))
    elif status.state is State.BLOCKED:
        actions += [("action.approve", {"artifact": name}) for name in status.blocked]
    elif status.state in RUNNABLE:
        actions.append(("action.run_task", {"task": task.name}))
    elif status.state in (State.AWAITING_APPROVAL, State.APPROVAL_EXPIRED):
        actions.append(("action.approve", {"artifact": task.outputs[0]}))
    return actions


def derive_status(task: Task, graph: TaskGraph, project: Project, store: StateStore) -> TaskStatus:
    status = _derive(task, graph, project, store)
    status.actions = suggest_actions(task, graph, project, status)
    return status


def _derive(task: Task, graph: TaskGraph, project: Project, store: StateStore) -> TaskStatus:
    run = store.latest_run(task.name)
    if run is not None and run.status in ("queued", "running"):
        return TaskStatus(task.name, State(run.status))

    missing, blocked = [], []
    for name in task.inputs:
        if not project.input_exists(name):
            missing.append(name)
            continue
        producer = graph.producer_of(name)
        if producer is not None and producer.gate is not Gate.NONE:
            rec = store.get_artifact(name)
            if rec is None or rec.approved_hash != project.input_hash(name):
                blocked.append(name)
    if missing:
        return TaskStatus(task.name, State.MISSING_INPUT, missing=missing)
    if blocked:
        return TaskStatus(task.name, State.BLOCKED, blocked=blocked)

    if not all(project.artifact_path(o).exists() for o in task.outputs):
        if run is not None and run.status == "failed":
            return TaskStatus(task.name, State.FAILED, error=run.error)
        return TaskStatus(task.name, State.READY)

    primary = task.outputs[0]
    rec = store.get_artifact(primary)
    if rec is None:
        return TaskStatus(task.name, State.UNREGISTERED)
    current_hash = project.artifact_hash(primary)
    inputs_fresh = rec.fingerprint == full_fingerprint(task, project)
    if rec.hash != current_hash:
        store.mark_edited(primary, current_hash)
    if not inputs_fresh:
        if task.gate is not Gate.NONE and rec.approved_hash is not None:
            return TaskStatus(task.name, State.APPROVAL_EXPIRED)
        return TaskStatus(task.name, State.STALE)
    if task.gate is Gate.NONE:
        return TaskStatus(task.name, State.DONE)
    if rec.approved_hash is None:
        return TaskStatus(task.name, State.AWAITING_APPROVAL)
    if rec.approved_hash == current_hash:
        return TaskStatus(task.name, State.DONE)
    return TaskStatus(task.name, State.APPROVAL_EXPIRED)


def status_board(graph: TaskGraph, project: Project, store: StateStore) -> list[TaskStatus]:
    return [derive_status(task, graph, project, store) for task in graph.tasks.values()]
