"""Run ffmpeg with progress and cancellation; escape paths for filter graphs (spec §6.4, §9.2)."""
from __future__ import annotations

import collections
import subprocess
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import PurePath

from lychnia.errors import Cancelled, TaskError

KILL_AFTER_S = 5.0


@dataclass(frozen=True)
class FfmpegResult:
    command: list[str]
    stderr_tail: str


def parse_progress_line(line: str) -> tuple[str, str] | None:
    key, sep, value = line.strip().partition("=")
    return (key, value) if sep else None


def run_ffmpeg(args: list[str], *, total_s: float | None = None,
               on_progress: Callable[[float], None] | None = None,
               cancel: threading.Event | None = None,
               ffmpeg_cmd: Sequence[str] = ("ffmpeg",),
               stderr_lines: int = 50, kill_after_s: float = KILL_AFTER_S) -> FfmpegResult:
    cmd = [*ffmpeg_cmd, "-nostdin", "-hide_banner", "-nostats", "-progress", "pipe:1", *args]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise TaskError("task.ffmpeg_missing", command=cmd) from exc

    if proc.stdout is None or proc.stderr is None:
        raise RuntimeError("ffmpeg pipes were not created")

    tail: collections.deque[str] = collections.deque(maxlen=stderr_lines)

    def drain_stderr() -> None:
        for line in proc.stderr:
            tail.append(line.rstrip("\r\n"))

    drainer = threading.Thread(target=drain_stderr, daemon=True)
    drainer.start()

    for line in proc.stdout:
        if cancel is not None and cancel.is_set():
            _terminate(proc, kill_after_s)
            drainer.join()
            raise Cancelled()
        kv = parse_progress_line(line)
        if kv and kv[0] == "out_time_us" and on_progress is not None and total_s:
            try:
                done_s = int(kv[1]) / 1_000_000
            except ValueError:
                continue
            on_progress(min(100.0, round(done_s / total_s * 100, 2)))
    code = proc.wait()
    drainer.join()
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    if code != 0:
        raise TaskError("task.ffmpeg_failed", command=cmd, stderr_tail="\n".join(tail), code=code)
    return FfmpegResult(cmd, "\n".join(tail))


def _terminate(proc: subprocess.Popen, kill_after_s: float) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=kill_after_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def filter_path(p: PurePath | str) -> str:
    """Path token for a filter option value (`subtitles=filename=<token>`).

    Forward slashes on every OS; the token is single-quoted so the filtergraph parser takes it
    literally, and `:` is escaped so the filter's own option parser does not split on it.
    A `'` inside the path closes the quote, escapes the quote and reopens.
    """
    text = PurePath(p).as_posix()
    text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'\\''")
    return f"'{text}'"
