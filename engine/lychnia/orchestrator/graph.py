"""Producers, dependencies, transitive closure and composite targets (spec §5, §6.3)."""
from __future__ import annotations

from collections.abc import Iterable

from lychnia.orchestrator.task import Task

TARGETS: dict[str, tuple[str, ...]] = {
    "prepare": ("transcribe", "camera_health"),
    "gate_a": ("callouts", "control_frames"),
    "video": ("segments", "preview"),
    "content": ("subtitles", "thumbnail", "blog"),
    "deliver": ("render", "shorts"),
}


class TaskGraph:
    def __init__(self, tasks: Iterable[Task], targets: dict[str, tuple[str, ...]] | None = None) -> None:
        self.tasks: dict[str, Task] = {}
        self._producers: dict[str, Task] = {}
        self.targets = TARGETS if targets is None else targets
        for task in tasks:
            if task.name in self.tasks:
                raise ValueError(f"duplicate task name: {task.name}")
            self.tasks[task.name] = task
            for out in task.outputs:
                if out in self._producers:
                    raise ValueError(f"artifact {out} produced by both {self._producers[out].name} and {task.name}")
                self._producers[out] = task

    def producer_of(self, name: str) -> Task | None:
        return self._producers.get(name)

    def dependencies(self, task: Task) -> list[Task]:
        deps: list[Task] = []
        for name in task.inputs:
            producer = self._producers.get(name)
            if producer is not None and not producer.on_demand and producer not in deps:
                deps.append(producer)
        return deps

    def closure(self, names: Iterable[str]) -> list[Task]:
        """Requested tasks and their transitive dependencies, dependencies first."""
        order: list[Task] = []
        seen: set[str] = set()

        def visit(task: Task) -> None:
            if task.name in seen:
                return
            seen.add(task.name)
            for dep in self.dependencies(task):
                visit(dep)
            order.append(task)

        for name in names:
            visit(self.tasks[name])
        return order

    def resolve_target(self, target: str) -> list[Task]:
        if target in self.targets:
            return self.closure(self.targets[target])
        if target in self.tasks:
            return self.closure([target])
        raise KeyError(target)
