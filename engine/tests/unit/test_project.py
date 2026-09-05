import threading

from lychnia.project.project import Project
from tests.unit.fakes import FAKE_ARTIFACTS


def test_project_paths_config_and_store(make_project):
    root = make_project()
    p = Project(root, artifacts=FAKE_ARTIFACTS)
    assert p.id == "2026-09-06_prueba"
    assert p.config.duration == 100.0
    assert p.artifact_path("x.txt") == root / "work" / "x.txt"
    assert p.artifact_path("np.txt") == root / "work" / "np.txt"
    assert p.store.get_artifact("x.txt") is None
    assert (root / ".lychnia" / "state.sqlite").exists()


def test_inputs_of_the_three_kinds(make_project):
    root = make_project()
    p = Project(root, artifacts=FAKE_ARTIFACTS)
    assert p.input_exists("config:cut") and not p.input_exists("config:shorts")
    assert p.input_hash("config:cut") is None
    assert not p.input_exists("source:master")
    (root / "input" / "audio").mkdir(parents=True)
    (root / "input" / "audio" / "m.mkv").write_bytes(b"m")
    assert p.input_exists("source:master")
    assert p.input_hash("source:master").startswith("sha256:")
    assert p.source_path("cam_b") is None and not p.input_exists("source:cam_b")
    assert not p.input_exists("x.txt") and p.artifact_hash("x.txt") is None
    p.artifact_path("x.txt").parent.mkdir(parents=True)
    p.artifact_path("x.txt").write_text("x", encoding="utf-8")
    assert p.input_exists("x.txt") and p.artifact_hash("x.txt") == p.input_hash("x.txt")


def test_slug_in_paths_and_reload(make_project):
    from lychnia.orchestrator.artifacts import ARTIFACTS
    root = make_project()
    p = Project(root)
    assert p.artifact_path("blog.src.mdx") == root / "blog" / "prueba.src.mdx"
    (root / "project.toml").write_text((root / "project.toml").read_text().replace('"prueba"', '"otro"'), encoding="utf-8")
    assert p.config.meta.slug == "prueba"     # cached
    p.reload()
    assert p.config.meta.slug == "otro"
    assert ARTIFACTS["final.mp4"].path == "video/final.mp4"


def test_config_never_returns_none_while_reloading(make_project):
    root = make_project()
    p = Project(root, artifacts=FAKE_ARTIFACTS)
    exceptions: list[Exception] = []

    def reloader():
        for _ in range(500):
            p.reload()

    def reader():
        try:
            for _ in range(500):
                assert p.config.meta.slug == "prueba"
        except Exception as exc:  # noqa: BLE001 - collected and asserted below
            exceptions.append(exc)

    threads = [threading.Thread(target=reloader)] + [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not exceptions, f"Exceptions occurred: {exceptions}"
