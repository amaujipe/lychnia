"""One sermon project on disk: config, paths, registry and artifact resolution."""
from __future__ import annotations

from pathlib import Path

from lychnia.orchestrator.artifacts import ARTIFACTS, CONFIG_PREFIX, SOURCE_PREFIX, ArtifactSpec, is_config, is_source
from lychnia.orchestrator.hashing import hash_file
from lychnia.orchestrator.state import StateStore
from lychnia.project.config import ProjectConfig, load_config
from lychnia.project.layout import ProjectPaths


class Project:
    def __init__(self, root: Path, master_limit: float | None = None,
                 artifacts: dict[str, ArtifactSpec] | None = None) -> None:
        self.root = Path(root).resolve()
        self.paths = ProjectPaths(self.root)
        self.master_limit = master_limit
        self.artifacts = ARTIFACTS if artifacts is None else artifacts
        self._config: ProjectConfig | None = None
        self._store: StateStore | None = None

    @property
    def id(self) -> str:
        return self.root.name

    @property
    def config(self) -> ProjectConfig:
        if self._config is None:
            self._config = load_config(self.paths.config_file, self.master_limit)
        return self._config

    def reload(self) -> None:
        self._config = None

    @property
    def store(self) -> StateStore:
        if self._store is None:
            self._store = StateStore(self.paths.state_db)
        return self._store

    # ── artifacts ────────────────────────────────────────────────────────
    def artifact_spec(self, name: str) -> ArtifactSpec:
        return self.artifacts[name]

    def artifact_path(self, name: str) -> Path:
        slug = self.config.meta.slug or self.root.name.partition("_")[2]
        return self.root / self.artifact_spec(name).path.format(slug=slug)

    def source_path(self, source: str) -> Path | None:
        rel = getattr(self.config.sources, source)
        return (self.root / rel) if rel else None

    def input_path(self, name: str) -> Path | None:
        if is_config(name):
            return None
        if is_source(name):
            return self.source_path(name[len(SOURCE_PREFIX):])
        return self.artifact_path(name)

    def input_exists(self, name: str) -> bool:
        if is_config(name):
            return self.config.has_input(name[len(CONFIG_PREFIX):])
        path = self.input_path(name)
        return path is not None and path.exists()

    def input_hash(self, name: str) -> str | None:
        path = self.input_path(name)
        if path is None or not path.exists():
            return None
        return hash_file(path)

    def artifact_hash(self, name: str) -> str | None:
        return self.input_hash(name)
