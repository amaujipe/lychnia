"""A graph node (spec §4). One subclass per row of the task table (§5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from lychnia.orchestrator.context import Context
    from lychnia.project.config import ProjectConfig


class Resource(str, Enum):
    GPU = "gpu"
    CPU_HEAVY = "cpu_heavy"
    LIGHT = "light"


class Gate(str, Enum):
    NONE = "none"
    A = "gate_a"
    B = "gate_b"


class Task(ABC):
    name: ClassVar[str]
    inputs: ClassVar[tuple[str, ...]] = ()      # artifact names, "source:x" or "config:section.field"
    outputs: ClassVar[tuple[str, ...]] = ()     # artifact names; outputs[0] carries the registry row
    resource: ClassVar[Resource] = Resource.LIGHT
    gate: ClassVar[Gate] = Gate.NONE
    on_demand: ClassVar[bool] = False           # never run because a consumer needs it (like `plan`)

    @abstractmethod
    def fingerprint(self, cfg: "ProjectConfig") -> str:
        """Deterministic string of the config fields that affect this task."""

    @abstractmethod
    def run(self, ctx: "Context") -> None:
        """Do the work; write every output through `ctx.output(name)`."""
