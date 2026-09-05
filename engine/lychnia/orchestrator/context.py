"""What a task receives when it runs (spec §6.4)."""
from __future__ import annotations

import threading
from pathlib import Path

from lychnia.errors import Cancelled, TaskError
from lychnia.orchestrator.events import EventBus
from lychnia.project.project import Project


class Context:
    def __init__(self, project: Project, run_id: int, bus: EventBus, cancel: threading.Event,
                 capabilities: dict | None = None, lang: str | None = None) -> None:
        self.project = project
        self.cfg = project.config            # captured now; later edits do not affect this run
        self.paths = project.paths
        self.master_limit = project.master_limit
        self.run_id = run_id
        self.bus = bus
        self.cancel = cancel
        self.capabilities = capabilities or {}
        self.lang = lang
        self.task_name = ""
        self.log_lines: list[str] = []
        self._partials: dict[str, tuple[Path, Path]] = {}

    # ── reporting ────────────────────────────────────────────────────────
    def log(self, msg: str) -> None:
        self.log_lines.append(msg)
        self.bus.publish("task.log", task=self.task_name, run=self.run_id, msg=msg)

    def progress(self, pct: float, eta_s: float | None = None) -> None:
        self.bus.publish("task.progress", task=self.task_name, run=self.run_id, pct=pct, eta_s=eta_s)

    def check_cancelled(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()

    # ── outputs ──────────────────────────────────────────────────────────
    def output(self, name: str) -> Path:
        """Path to write `name` to. Renamed to its final name by `commit()`."""
        final = self.project.artifact_path(name)
        final.parent.mkdir(parents=True, exist_ok=True)
        partial = final.with_name(final.name + ".partial")
        self._partials[name] = (partial, final)
        return partial

    def commit(self) -> list[Path]:
        for name, (partial, final) in self._partials.items():
            if not partial.exists():
                self.abort()
                raise TaskError("task.output_missing", artifact=name)
        finals = []
        for partial, final in self._partials.values():
            partial.replace(final)
            finals.append(final)
        self._partials.clear()
        return finals

    def abort(self) -> None:
        for partial, _ in self._partials.values():
            partial.unlink(missing_ok=True)
        self._partials.clear()
