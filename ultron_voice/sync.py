"""FFmpeg sync and composition helpers (dub + audiobook).

Dub:
  1. segment audio into pieces,
  2. synthesize translated text per piece,
  3. stretch each piece to the original segment duration,
  4. concat -> dubbed audio,
  5. mux video stream + dubbed audio.

Audiobook:
  1. synthesize each chapter to its own audio,
  2. concat chapter audios -> single mixed audio.
"""

from __future__ import annotations

import ffmpeg
from pathlib import Path


def pad_audio_to_duration(input_path: Path, output_path: Path, duration: float) -> None:
    """Pad (apad) an audio file to exactly ``duration`` seconds."""
    (
        ffmpeg.input(str(input_path))
        .filter("apad", whole_dur=str(duration))
        .output(
            str(output_path),
            ar=44100,
            ac=2,
            format="wav",
            loglevel="error",
        )
        .run(overwrite_output=True)
    )


def concatenate_audios(paths: list[Path], output_path: Path) -> None:
    """Concatenate WAV files into one audio file."""
    if not paths:
        raise ValueError("nenhum audio para concatenar")
    list_file = output_path.with_suffix(".txt")
    with list_file.open("w", encoding="utf-8") as fh:
        for p in paths:
            fh.write(f"file '{p.as_posix()}'\n")
    (
        ffmpeg.input(str(list_file), format="concat", safe=0)
        .output(
            str(output_path),
            ar=44100,
            ac=2,
            format="wav",
            loglevel="error",
        )
        .run(overwrite_output=True)
    )
    list_file.unlink(missing_ok=True)


def compose_dub_video(video_path: Path, dubbed_audio_path: Path, output_path: Path) -> Path:
    """Mux a video (no audio) with a dubbed audio track.

    The audio is already timed to the video, so the output is a synced dub.
    """
    # Video only (strip original audio).
    video_only = video_path.with_suffix(".video_only.mkv")
    (
        ffmpeg.input(str(video_path))
        .output(str(video_only), c="copy", loglevel="error")
        .run(overwrite_output=True)
    )
    try:
        (
            ffmpeg.input(str(video_only))
            .input(str(dubbed_audio_path))
            .output(
                str(output_path),
                codec="copy",
                audio_codec="aac",
                shortest=True,
                loglevel="error",
            )
            .run(overwrite_output=True)
        )
    finally:
        video_only.unlink(missing_ok=True)
    return output_path
