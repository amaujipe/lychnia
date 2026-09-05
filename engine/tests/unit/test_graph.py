import pytest

from lychnia.orchestrator.artifacts import ARTIFACTS, is_config, is_source
from lychnia.orchestrator.graph import TARGETS, TaskGraph
from tests.unit.fakes import FAKE_TARGETS, MakeP, MakeX, MakeY, MakeZ, NeedsP


def test_registry_has_the_spec_names():
    for name in ["transcript.srt", "transcript.tsv", "camera_health.txt", "camera_plan.json", "silences.raw.txt",
                 "outline.md", "callouts.toml", "callouts.ass", "callouts_render.ass", "control_sheets.txt",
                 "segments.txt", "preview.mp4", "final.mp4", "final.srt", "shorts.txt", "background.png",
                 "background-prompt.md", "thumbnail.jpg", "thumbnail-1280.jpg", "youtube.md",
                 "shorts-metadata.md", "blog.src.mdx", "blog.mdx"]:
        assert name in ARTIFACTS, name
    assert ARTIFACTS["callouts.toml"].providable and not ARTIFACTS["callouts.ass"].providable
    assert ARTIFACTS["blog.src.mdx"].path == "blog/{slug}.src.mdx"
    assert is_source("source:master") and is_config("config:cut") and not is_source("x.txt")


def test_composite_targets_match_the_spec():
    assert TARGETS["prepare"] == ("transcribe", "camera_health")
    assert TARGETS["gate_a"] == ("callouts", "control_frames")
    assert TARGETS["video"] == ("segments", "preview")
    assert TARGETS["content"] == ("subtitles", "thumbnail", "blog")
    assert TARGETS["deliver"] == ("render", "shorts")


def test_producers_and_dependencies():
    g = TaskGraph([MakeX(), MakeY(), MakeZ()])
    assert g.producer_of("y.txt").name == "make_y"
    assert g.producer_of("given.txt") is None
    assert g.producer_of("config:cut") is None
    assert [t.name for t in g.dependencies(g.tasks["make_z"])] == ["make_y"]


def test_closure_is_topological_and_skips_on_demand_producers():
    g = TaskGraph([MakeX(), MakeY(), MakeZ(), MakeP(), NeedsP()])
    assert [t.name for t in g.closure(["make_z"])] == ["make_x", "make_y", "make_z"]
    assert [t.name for t in g.closure(["needs_p"])] == ["needs_p"]          # make_p only on demand
    assert [t.name for t in g.closure(["make_p"])] == ["make_x", "make_p"]  # explicit request includes it


def test_resolve_target_accepts_composites_and_single_tasks():
    g = TaskGraph([MakeX(), MakeY(), MakeZ()], targets=FAKE_TARGETS)
    assert [t.name for t in g.resolve_target("all")] == ["make_x", "make_y", "make_z"]
    assert [t.name for t in g.resolve_target("xy")] == ["make_x", "make_y"]
    assert [t.name for t in g.resolve_target("make_y")] == ["make_x", "make_y"]
    with pytest.raises(KeyError):
        g.resolve_target("nope")


def test_duplicate_producer_is_rejected():
    class Other(MakeX):
        name = "other"
    with pytest.raises(ValueError):
        TaskGraph([MakeX(), Other()])
