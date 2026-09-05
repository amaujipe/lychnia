import os
import sys
import threading
import time
from pathlib import PurePosixPath, PureWindowsPath

import pytest

from lychnia.errors import Cancelled, TaskError
from lychnia.media.ffmpeg import filter_path, parse_progress_line, run_ffmpeg

FAKE_OK = """import sys, time
for i in range(1, 5):
    print(f"out_time_us={i * 1000000}", flush=True)
    print("progress=continue", flush=True)
    time.sleep(0.02)
print("out_time_us=N/A", flush=True)
print("progress=end", flush=True)
print("a warning line", file=sys.stderr)
"""

FAKE_FAIL = """import sys
for i in range(60):
    print(f"err {i}", file=sys.stderr)
sys.exit(3)
"""

FAKE_FOREVER = """import time
while True:
    print("out_time_us=1000000", flush=True)
    time.sleep(0.02)
"""


def _fake(tmp_path, code):
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(code, encoding="utf-8")
    return (sys.executable, str(script))


def test_parse_progress_line():
    assert parse_progress_line("out_time_us=1500000\n") == ("out_time_us", "1500000")
    assert parse_progress_line("progress=end") == ("progress", "end")
    assert parse_progress_line("garbage") is None


def test_progress_callback_and_result(tmp_path):
    seen = []
    result = run_ffmpeg(["-i", "x"], total_s=4.0, on_progress=seen.append, ffmpeg_cmd=_fake(tmp_path, FAKE_OK))
    assert seen == [25.0, 50.0, 75.0, 100.0]
    assert result.command[-2:] == ["-i", "x"] and "-progress" in result.command and "pipe:1" in result.command
    assert result.stderr_tail == "a warning line"


def test_failure_keeps_the_last_50_stderr_lines(tmp_path):
    with pytest.raises(TaskError) as exc:
        run_ffmpeg(["-i", "x"], ffmpeg_cmd=_fake(tmp_path, FAKE_FAIL))
    err = exc.value
    assert err.key == "task.ffmpeg_failed" and err.params["code"] == 3
    lines = err.stderr_tail.splitlines()
    assert len(lines) == 50 and lines[0] == "err 10" and lines[-1] == "err 59"
    assert err.command[0] == sys.executable


def test_cancel_terminates_the_process(tmp_path):
    cancel = threading.Event()
    threading.Timer(0.1, cancel.set).start()
    t0 = time.time()
    with pytest.raises(Cancelled):
        run_ffmpeg([], cancel=cancel, ffmpeg_cmd=_fake(tmp_path, FAKE_FOREVER))
    assert time.time() - t0 < 4


@pytest.mark.skipif(sys.platform == "win32", reason="signal 0 probe is POSIX-only")
def test_progress_callback_exception_terminates_the_child(tmp_path):
    pid_file = tmp_path / "pid.txt"
    code = f"""import os, time
with open({str(pid_file)!r}, "w") as f:
    f.write(str(os.getpid()))
while True:
    print("out_time_us=1000000", flush=True)
    time.sleep(0.02)
"""

    def boom(pct):
        raise ValueError("cb boom")

    t0 = time.time()
    with pytest.raises(ValueError):
        run_ffmpeg([], total_s=10.0, on_progress=boom, ffmpeg_cmd=_fake(tmp_path, code))
    assert time.time() - t0 < 4

    pid = int(pid_file.read_text().strip())
    deadline = time.time() + 2
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_missing_binary():
    with pytest.raises(TaskError) as exc:
        run_ffmpeg([], ffmpeg_cmd=("definitely-not-ffmpeg-binary",))
    assert exc.value.key == "task.ffmpeg_missing"


def test_filter_path_on_the_three_systems():
    assert filter_path(PureWindowsPath(r"C:\Users\a\callouts.ass")) == r"'C\:/Users/a/callouts.ass'"
    assert filter_path(PurePosixPath("/home/a/callouts.ass")) == "'/home/a/callouts.ass'"
    assert filter_path(PurePosixPath("/Users/a/Library/x.ass")) == "'/Users/a/Library/x.ass'"
    assert filter_path(PurePosixPath("/tmp/a b/x.ass")) == "'/tmp/a b/x.ass'"
    assert filter_path(PurePosixPath("/tmp/a:b/x.ass")) == r"'/tmp/a\:b/x.ass'"
    assert filter_path(PurePosixPath("/tmp/o'k/x.ass")) == r"'/tmp/o\'\''k/x.ass'"
