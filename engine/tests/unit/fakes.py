"""Fake tasks for orchestrator tests. They write small text files."""
from __future__ import annotations

from lychnia.orchestrator.artifacts import ArtifactSpec
from lychnia.orchestrator.task import Gate, Resource, Task

FAKE_ARTIFACTS = {a.name: a for a in [
    ArtifactSpec("x.txt", "work/x.txt"),
    ArtifactSpec("y.txt", "work/y.txt"),
    ArtifactSpec("z.txt", "work/z.txt"),
    ArtifactSpec("p.txt", "work/p.txt"),
    ArtifactSpec("np.txt", "work/np.txt"),
    ArtifactSpec("given.txt", "work/given.txt", providable=True),
]}


class MakeX(Task):
    name = "make_x"
    inputs = ("config:cut",)
    outputs = ("x.txt",)
    resource = Resource.LIGHT
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return cfg.cut_fingerprint

    def run(self, ctx):
        ctx.output("x.txt").write_text("x", encoding="utf-8")


class MakeY(Task):
    """Gated: its consumers wait for approval of y.txt."""
    name = "make_y"
    inputs = ("x.txt",)
    outputs = ("y.txt",)
    resource = Resource.CPU_HEAVY
    gate = Gate.A

    def fingerprint(self, cfg):
        return "y"

    def run(self, ctx):
        ctx.output("y.txt").write_text("y", encoding="utf-8")


class MakeZ(Task):
    name = "make_z"
    inputs = ("y.txt", "given.txt")
    outputs = ("z.txt",)
    resource = Resource.CPU_HEAVY
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "z"

    def run(self, ctx):
        ctx.output("z.txt").write_text("z", encoding="utf-8")


class MakeP(Task):
    """On demand only, like `plan`."""
    name = "make_p"
    inputs = ("x.txt",)
    outputs = ("p.txt",)
    resource = Resource.LIGHT
    gate = Gate.A
    on_demand = True

    def fingerprint(self, cfg):
        return "p"

    def run(self, ctx):
        ctx.output("p.txt").write_text("p", encoding="utf-8")


class NeedsP(Task):
    name = "needs_p"
    inputs = ("p.txt",)
    outputs = ("np.txt",)
    resource = Resource.GPU
    gate = Gate.NONE

    def fingerprint(self, cfg):
        return "np"

    def run(self, ctx):
        ctx.output("np.txt").write_text("z", encoding="utf-8")


FAKE_TARGETS = {"all": ("make_z",), "xy": ("make_x", "make_y")}
