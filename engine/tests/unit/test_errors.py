from lychnia.errors import Cancelled, ConfigError, LychniaError, TaskError


def test_config_error_carries_field_and_key():
    err = ConfigError("cut.end", "validation.cut_end_before_start")
    assert err.field == "cut.end"
    assert err.key == "validation.cut_end_before_start"
    assert err.params["field"] == "cut.end"
    assert isinstance(err, LychniaError)


def test_task_error_keeps_command_and_stderr():
    err = TaskError("task.ffmpeg_failed", command=["ffmpeg", "-i", "x"], stderr_tail="boom", code=1)
    assert err.command == ["ffmpeg", "-i", "x"]
    assert err.stderr_tail == "boom"
    assert err.params == {"code": 1}


def test_cancelled_has_key():
    assert Cancelled().key == "task.cancelled"
