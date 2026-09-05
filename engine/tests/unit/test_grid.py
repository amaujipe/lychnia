from lychnia.media.grid import FPS, f30, frames_for, on_grid


def test_fps_is_30():
    assert FPS == 30


def test_f30_snaps_to_the_frame_grid():
    assert f30(632.8) == 632.8
    assert f30(649.2666) == 649.266667
    assert f30(700) == 700.0


def test_on_grid():
    assert on_grid(649.266667)
    assert not on_grid(649.27)


def test_frames_for_full_sermon_and_limited_run():
    assert frames_for(4685.0) == 140550
    assert frames_for(142.5) == 4275
