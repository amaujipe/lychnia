"""The canonical voice chain (hard rule 7). Lives once, here.

Per sermon only three knobs change: the downmix to mono, an optional delay and
the loudness target. The final `aresample=48000` is not optional: loudnorm
resamples to 192 kHz internally and the AAC track would end up at 96 kHz.
"""
from __future__ import annotations

DOWNMIX: dict[str, str] = {
    "dual-mono": "pan=mono|c0=0.5*c0+0.5*c1",   # both channels equal: average them
    "left": "pan=mono|c0=c0",                   # voice only on L
    "right": "pan=mono|c0=c1",
}

_CHAIN = ("highpass=f=80,"
          "speechnorm=e=12.5:r=0.0008:l=1,"
          "alimiter=limit=0.85,"
          "loudnorm=I={lufs}:TP=-1.5:LRA=11,"
          "aresample=192000,"           # 4x oversampling to see the true peak
          "alimiter=limit=0.95,"        # limits the real inter-sample peak
          "aresample=48000")            # delivery sample rate


def voice_filter(downmix: str, lufs: float, delay_ms: int = 0) -> str:
    """Full `-af` value: downmix, optional delay, canonical chain."""
    parts = [DOWNMIX[downmix]]
    if delay_ms:
        parts.append(f"adelay={delay_ms}:all=1")
    parts.append(_CHAIN.format(lufs=f"{lufs:g}"))
    return ",".join(parts)
