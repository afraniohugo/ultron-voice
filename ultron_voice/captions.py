"""Caption generation and overlay (dub pipeline).

A SRT file is produced from the segment boundaries and overlaid on the final
video with the ``subtitles`` filter. Tests can also emit the SRT text directly
without rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SRT_HEADING = "Dubbed captions"


@dataclass(frozen=True)
class Caption:
    index: int
    start: float
    end: float
    text: str


def format_time(seconds: float) -> str:
    total = round(max(0.0, seconds), 3)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"


def build_subtitles(segments: list[Segment], captions: list[Caption]) -> Path:
    """Write *captions* (already aligned to *segments*) to an SRT file.

    ``segments`` provides the absolute timeline; *captions* carry the text.
    """
    if len(captions) != len(segments):
        raise ValueError("quantidade de legendas distante do numero de segmentos")
    srt_path = segments[0].path.parent / "captions.srt"
    lines: list[str] = []
    for i, cap in enumerate(captions, start=1):
        lines.append(str(i))
        lines.append(f"{format_time(cap.start)} --> {format_time(cap.end)}")
        lines.append(cap.text)
        lines.append("")
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return srt_path


def overlay_subtitles(input_video: Path, srt: Path, output: Path) -> Path:
    """Render the SRT onto the video stream."""
    (
        ffmpeg.input(str(input_video))
        .filter(
            "subtitles",
            filename=str(srt),
            force_style='Fontsize=28,MarginV=40,FontName=/windows/Fonts/arial.ttf',
        )
        .output(
            str(output), c="copy", loglevel="error",
        )
        .run(overwrite_output=True)
    )
    return output
