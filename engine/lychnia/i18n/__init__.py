"""Operator-facing strings. Keys are English snake_case, dotted by section.

Spanish (`es`) is the default and ships with the Engine; English (`en`) ships too.
Developer logs and exception internals stay in English and never come through here.
"""
from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from importlib import resources

DEFAULT_LANG = "es"


def flatten(table: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in table.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, full))
        else:
            out[full] = str(value)
    return out


def available_languages() -> list[str]:
    files = resources.files(__package__)
    return sorted(p.name.removesuffix(".toml") for p in files.iterdir() if p.name.endswith(".toml"))


@lru_cache(maxsize=None)
def load_messages(lang: str) -> dict[str, str]:
    text = resources.files(__package__).joinpath(f"{lang}.toml").read_text(encoding="utf-8")
    return flatten(tomllib.loads(text))


def current_language() -> str:
    return os.environ.get("LYCHNIA_LANG", DEFAULT_LANG)


def t(key: str, lang: str | None = None, **params: object) -> str:
    """Translate `key`. Unknown keys raise KeyError so tests catch them early."""
    messages = load_messages(lang or current_language())
    if key not in messages:
        raise KeyError(f"i18n key not found: {key}")
    return messages[key].format(**params)
