"""Edit `project.toml` by sections, preserving the operator's comments (tomlkit)."""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomlkit
from tomlkit.items import AoT

from lychnia.errors import ConfigError
from lychnia.project.config import ProjectConfig, parse_config


def read_raw(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def patch_config(path: Path, patch: dict[str, dict[str, object]],
                 master_limit: float | None = None) -> ProjectConfig:
    """Apply `{section: {field: value}}`, validate, then write atomically.

    Only scalar values inside plain tables are supported. An array-of-tables
    section (`[[section]]`) and a dict/list patch value are both rejected with
    a `ConfigError` — patching those field by field would either crash on a
    tomlkit implementation detail or silently drop the sub-table's comments.
    """
    path = Path(path)
    doc = tomlkit.parse(read_raw(path))
    for section, fields in patch.items():
        if section in doc and isinstance(doc[section], AoT):
            raise ConfigError(section, "validation.unsupported_patch_section", section=section)
        if section not in doc:
            doc.add(section, tomlkit.table())
        for key, value in fields.items():
            if isinstance(value, (dict, list)):
                raise ConfigError(f"{section}.{key}", "validation.unsupported_patch_value")
            doc[section][key] = value
    text = tomlkit.dumps(doc)
    cfg = parse_config(tomllib.loads(text), master_limit)   # raises ConfigError, file untouched
    partial = path.with_name(path.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)
    return cfg
