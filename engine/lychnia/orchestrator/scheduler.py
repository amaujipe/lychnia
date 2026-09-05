"""Queue with three lanes and a coordinator that walks the graph (spec §6.3, §6.4)."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field

from lychnia.errors import Cancelled
from lychnia.orchestrator.context import Context
from lychnia.orchestrator.events import EventBus
from lychnia.orchestrator.graph import TaskGraph
from lychnia.orchestrator.hashing import hash_file
from lychnia.orchestrator.status import RUNNABLE, State, TaskStatus, derive_status, full_fingerprint
from lychnia.orchestrator.task import Resource, Task
from lychnia.project.project import Project

LANE_CAPACITY: dict[Resource, int] = {Resource.GPU: 1, Resource.CPU_HEAVY: 1, Resource.LIGHT: 4}


@dataclass
class RunReport:
    started: list[int] = field(default_factory=list)
    blocked: list[TaskStatus] = field(default_factory=list)
    error: str | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)


@dataclass
class _Active:
    task: Task
    cancel: threading.Event
    thread: threading.Thread


class Scheduler:
    def __init__(self, graph: TaskGraph, project: Project, bus: EventBus,
                 lanes: dict[Resource, int] | None = None, capabilities: dict | None = None,
                 lang: str | None = None) -> None:
        self.graph = graph
        self.project = project
        self.bus = bus
        self.capabilities = capabilities or {}
        self.lang = lang
        self.lanes = {res: threading.Semaphore(n) for res, n in (lanes or LANE_CAPACITY).items()}
        self._active: dict[int, _Active] = {}
        self._lock = threading.Lock()

    # ── public API ───────────────────────────────────────────────────────
    def run_target(self, target: str, wait: bool = False) -> RunReport:
        return self._coordinate(self.graph.resolve_target(target), wait)

    def run_task(self, name: str, wait: bool = False) -> RunReport:
        return self._coordinate(self.graph.closure([name]), wait)

    def cancel(self, run_id: int) -> bool:
        with self._lock:
            active = self._active.get(run_id)
        if active is None:
            return False
        active.cancel.set()
        return True

    def active_runs(self) -> list[int]:
        with self._lock:
            return list(self._active)

    def shutdown(self) -> None:
        with self._lock:
            actives = list(self._active.values())
        for active in actives:
            active.cancel.set()
        for active in actives:
            active.thread.join()

    # ── coordinator ──────────────────────────────────────────────────────
    def _coordinate(self, tasks: list[Task], wait: bool) -> RunReport:
        report = RunReport()
        pending = {t.name: t for t in tasks}
        mine: set[int] = set()
        done: queue.Queue[int] = queue.Queue()

        def loop() -> None:
            try:
                store = self.project.store
                while pending or mine:
                    self.project.reload()
                    for name, task in list(pending.items()):
                        status = derive_status(task, self.graph, self.project, store)
                        if status.state in RUNNABLE:
                            pending.pop(name)
                            run_id = self._launch(task, done)
                            report.started.append(run_id)
                            mine.add(run_id)
                        elif status.state in (State.MISSING_INPUT, State.BLOCKED):
                            needs = status.missing + status.blocked
                            producers = {p.name for n in needs if (p := self.graph.producer_of(n)) is not None}
                            with self._lock:
                                active_names = {a.task.name for rid, a in self._active.items() if rid in mine}
                            if not producers & (set(pending) | active_names):
                                pending.pop(name)
                                report.blocked.append(status)
                        elif status.state not in (State.QUEUED, State.RUNNING):
                            pending.pop(name)          # done, awaiting approval, approval expired
                    if not mine:
                        if pending:                    # nothing runnable and nothing running: give up
                            for name, task in list(pending.items()):
                                report.blocked.append(derive_status(task, self.graph, self.project, store))
                            pending.clear()
                        break
                    finished = done.get()
                    mine.discard(finished)
            except Exception as exc:  # noqa: BLE001 - the coordinator must never hang the waiter
                report.error = f"{type(exc).__name__}: {exc}"
                self.bus.publish("scheduler.failed", error=report.error)
            finally:
                report._done.set()

        thread = threading.Thread(target=loop, name="lychnia-coordinator", daemon=True)
        thread.start()
        if wait:
            report.wait()
        return report

    # ── one run ──────────────────────────────────────────────────────────
    def _launch(self, task: Task, done: "queue.Queue[int]") -> int:
        store = self.project.store
        run_id = store.start_run(task.name, self.project.master_limit)
        log_path = self.project.paths.logs / f"{run_id}.log"
        store.set_run_log(run_id, log_path.relative_to(self.project.root).as_posix())
        # Captured before the task runs: the fingerprint and the output paths must reflect the
        # inputs and config as they stood when the run was launched, not whatever the coordinator
        # (running concurrently) reloads afterwards (hard rule 10).
        fingerprint = full_fingerprint(task, self.project)
        output_paths = {name: self.project.artifact_path(name) for name in task.outputs}
        cancel = threading.Event()
        ctx = Context(self.project, run_id, self.bus, cancel, self.capabilities, self.lang)
        ctx.task_name = task.name

        def work() -> None:
            try:
                ctx.check_cancelled()
                with self.lanes[task.resource]:
                    store.set_run_status(run_id, "running")
                    self.bus.publish("task.started", task=task.name, run=run_id)
                    ctx.check_cancelled()
                    task.run(ctx)
                    ctx.commit()
                    for name, path in output_paths.items():
                        store.record_artifact(name, path.relative_to(self.project.root).as_posix(),
                                              hash_file(path) if path.exists() else None, fingerprint, task.name)
                        self.bus.publish("artifact.changed", artifact=name, producer=task.name, run=run_id)
                    store.finish_run(run_id, "done")
                    self.bus.publish("task.finished", task=task.name, run=run_id)
            except Cancelled:
                ctx.abort()
                store.finish_run(run_id, "cancelled")
                self.bus.publish("task.failed", task=task.name, run=run_id, reason="cancelled")
            except Exception as exc:  # noqa: BLE001 - every failure must be recorded
                ctx.abort()
                store.finish_run(run_id, "failed", error=f"{type(exc).__name__}: {exc}")
                self.bus.publish("task.failed", task=task.name, run=run_id, reason="error",
                                 error=f"{type(exc).__name__}: {exc}")
            finally:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text("\n".join(ctx.log_lines) + ("\n" if ctx.log_lines else ""), encoding="utf-8")
                with self._lock:
                    self._active.pop(run_id, None)
                done.put(run_id)

        thread = threading.Thread(target=work, name=f"lychnia-{task.name}-{run_id}", daemon=True)
        with self._lock:
            self._active[run_id] = _Active(task, cancel, thread)
        thread.start()
        return run_id
