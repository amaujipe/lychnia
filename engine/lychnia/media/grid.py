"""The 1/30 s frame grid (hard rule 2).

Segments are cut by exact frame count (`-frames:v round(dur*30)`), so every shot
boundary must sit on a multiple of 1/30 s or the residue accumulates as drift.
"""
from __future__ import annotations

FPS = 30


def f30(t: float) -> float:
    """Snap a time in seconds to the frame grid."""
    return round(round(t * FPS) / FPS, 6)


def on_grid(t: float, tol: float = 1e-4) -> bool:
    return abs(round(t * FPS) - t * FPS) < tol


def frames_for(duration: float) -> int:
    return int(round(duration * FPS))
