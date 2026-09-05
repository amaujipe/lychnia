"""Exceptions that carry an operator-facing i18n message key.

The exception text itself stays English (developer-facing); the operator sees
`lychnia.i18n.t(err.key, **err.params)`.
"""
from __future__ import annotations


class LychniaError(Exception):
    """Base error. `key` is an i18n key; `params` fill its placeholders."""

    def __init__(self, key: str, **params: object) -> None:
        self.key = key
        self.params = params
        super().__init__(f"{key} {params}" if params else key)


class ConfigError(LychniaError):
    """A project.toml field is missing or invalid. `field` is the dotted TOML path."""

    def __init__(self, field: str, key: str, **params: object) -> None:
        self.field = field
        super().__init__(key, field=field, **params)


class TaskError(LychniaError):
    """A task cannot start or failed. Keeps the failing command and its stderr tail."""

    def __init__(self, key: str, *, command: list[str] | None = None,
                 stderr_tail: str = "", **params: object) -> None:
        self.command = command
        self.stderr_tail = stderr_tail
        super().__init__(key, **params)


class Cancelled(LychniaError):
    """The operator cancelled the run."""

    def __init__(self) -> None:
        super().__init__("task.cancelled")
