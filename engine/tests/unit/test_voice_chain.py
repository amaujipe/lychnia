import pytest

from lychnia.media.voice_chain import DOWNMIX, voice_filter

ORIGINAL_AF_VOZ = ("pan=mono|c0=0.5*c0+0.5*c1,highpass=f=80,speechnorm=e=12.5:r=0.0008:l=1,"
                   "alimiter=limit=0.85,loudnorm=I=-15:TP=-1.5:LRA=11,aresample=192000,"
                   "alimiter=limit=0.95,aresample=48000")


def test_default_chain_matches_the_original_cfg_af_voz():
    assert voice_filter("dual-mono", -15) == ORIGINAL_AF_VOZ


def test_chain_always_ends_with_48k_resample():
    for downmix in DOWNMIX:
        assert voice_filter(downmix, -16, 20).endswith("aresample=48000")


def test_delay_goes_right_after_the_downmix():
    af = voice_filter("left", -15, 20)
    assert af.startswith("pan=mono|c0=c0,adelay=20:all=1,highpass=f=80,")


def test_unknown_downmix_raises():
    with pytest.raises(KeyError):
        voice_filter("stereo", -15)
