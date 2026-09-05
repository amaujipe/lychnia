import sqlite3

from lychnia.orchestrator.state import StateStore


def test_artifact_roundtrip_and_approval(tmp_path):
    store = StateStore(tmp_path / ".lychnia" / "state.sqlite")
    assert store.get_artifact("camera_plan.json") is None
    store.record_artifact("camera_plan.json", "outline/camera_plan.json", "sha256:aa", "fp1", "plan")
    rec = store.get_artifact("camera_plan.json")
    assert (rec.hash, rec.fingerprint, rec.producer, rec.approved_hash, rec.edited) == ("sha256:aa", "fp1", "plan", None, False)
    store.approve("camera_plan.json", "sha256:aa", "andres")
    rec = store.get_artifact("camera_plan.json")
    assert rec.approved_hash == "sha256:aa" and rec.approved_by == "andres" and rec.approved_at
    store.mark_edited("camera_plan.json", "sha256:bb")
    rec = store.get_artifact("camera_plan.json")
    assert rec.edited is True and rec.hash == "sha256:bb" and rec.approved_hash == "sha256:aa"
    store.revoke_approval("camera_plan.json")
    assert store.get_artifact("camera_plan.json").approved_hash is None
    assert [a.name for a in store.list_artifacts()] == ["camera_plan.json"]


def test_recording_again_replaces_but_keeps_approval(tmp_path):
    store = StateStore(tmp_path / "s.sqlite")
    store.record_artifact("x", "x", "h1", "f1", "t")
    store.approve("x", "h1", "a")
    store.record_artifact("x", "x", "h2", "f2", "t")
    rec = store.get_artifact("x")
    assert (rec.hash, rec.fingerprint, rec.approved_hash, rec.edited) == ("h2", "f2", "h1", False)


def test_runs_and_events(tmp_path):
    store = StateStore(tmp_path / "s.sqlite")
    assert store.latest_run("render") is None
    r1 = store.start_run("render", master_limit=700, log_path=".lychnia/logs/1.log")
    run = store.latest_run("render")
    assert run.id == r1 and run.status == "queued" and run.master_limit == 700 and run.finished_at is None
    store.set_run_status(r1, "running")
    assert store.get_run(r1).status == "running"
    store.add_event(r1, "task.progress", {"pct": 50})
    store.finish_run(r1, "failed", error="boom")
    run = store.get_run(r1)
    assert run.status == "failed" and run.error == "boom" and run.finished_at
    r2 = store.start_run("render")
    assert store.latest_run("render").id == r2
    assert store.events_for(r1) == [("task.progress", store.events_for(r1)[0][1], {"pct": 50})]


def test_store_can_be_deleted_and_recreated(tmp_path):
    p = tmp_path / "s.sqlite"
    store = StateStore(p)
    store.record_artifact("x", "x", "h", "f", "t")
    store.close()
    p.unlink()
    store2 = StateStore(p)
    assert store2.get_artifact("x") is None
    assert sqlite3.connect(p).execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
