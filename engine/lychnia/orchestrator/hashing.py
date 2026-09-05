"""Content hashes for the artifact registry (spec §6.1).

Small files (TOML, SRT, JSON, ASS): full SHA-256. Large media files: size, mtime and
the SHA-256 of the first and last 8 MiB, so a 5 GB master hashes in milliseconds.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

LARGE_THRESHOLD = 64 * 2**20
EDGE_BYTES = 8 * 2**20


def hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: Path, large_threshold: int = LARGE_THRESHOLD) -> str:
    path = Path(path)
    stat = path.stat()
    digest = hashlib.sha256()
    if stat.st_size <= large_threshold:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return "sha256:" + digest.hexdigest()
    digest.update(f"{stat.st_size}|{stat.st_mtime_ns}|".encode())
    with path.open("rb") as fh:
        digest.update(fh.read(EDGE_BYTES))
        fh.seek(max(stat.st_size - EDGE_BYTES, 0))
        digest.update(fh.read(EDGE_BYTES))
    return "large:" + digest.hexdigest()
