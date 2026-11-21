"""Audio / video segmentation.

Splitting is done with FFmpeg:
  * ``fixed``  -> constant-duration chunks (deterministic, default).
  * ``silence``-> boundaries from the silencedetect filter.

Only ``fixed`` is exercised by default: it is deterministic, simple and fast.
"""

from __future__ import annotations

import ffmpeg
from dataclasses import dataclass
from pathlib import Path

SEGMENT_FIXED_DURATION = 15.0


@dataclass(frozen=True)
class Segment:
    index: int
    start: float
    end: float
    path: Path


def _probe_audio_duration(path: Path) -> float:
    result = (
        ffmpeg.input(str(path))
        .stream("audio")
        .output("pipe:", format="null", v=0)
        .run(cmd=["ffprobe", "-v", "quiet", "-print_format", "json"], capture_stdout=True)
    )
    import json
    return float((json.loads(result.stdout or "{}").get("streams") or [{}])[0].get("duration", 0.0))


def segment_audio_fixed(
    audio_path: Path,
    out_dir: Path,
    *,
    duration: float = SEGMENT_FIXED_DURATION,
    pad: float = 0.3,
) -> list[Segment]:
    """Split an audio file into fixed-duration chunks.

    Returns *Segment* descriptors with absolute *start*/*end* times and the
    piece written to disk.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    total = _probe_audio_duration(audio_path)
    segments: list[Segment] = []
    for i in range(0, int(total), int(duration)):
        start = round(i, 3)
        end = min(round(i + duration, 3), round(total, 3))
        if end - start < 0.1:
            continue
        piece = out_dir / f"seg_{len(segments):03d}.wav"
        (
            ffmpeg.input(str(audio_path), ss=start)
            .output(
                str(piece),
                ar=44100,
                ac=2,
                format="wav",
                loglevel="error",
            )
            .run(overwrite_output=True)
        )
        segments.append(Segment(index=len(segments), start=start, end=end, path=piece))
    return segments
