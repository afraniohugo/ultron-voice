"""Media probing, checksum and container helpers (FFprobe/FFmpeg)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

FFPROBE = "ffprobe"
FFMPEG = "ffmpeg"


@dataclass(frozen=True)
class MediaProbe:
    """Lightweight probe result for a media file."""

    path: Path
    duration: float
    width: int | None
    height: int | None
    codec_audio: str | None
    codec_video: str | None
    has_video: bool
    size_bytes: int


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, check=check
    )


def probe(path: Path) -> MediaProbe:
    """Run ffprobe and return a MediaProbe."""
    cmd = [
        FFPROBE,
        "-v", "error",
        "-show_entries", "format=duration,bit_rate,size",
        "-show_entries", "stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(path),
    ]
    res = _run(cmd)
    if res.returncode != 0:
        raise FileNotFoundError(
            f"ffprobe falhou em {path}: {res.stderr.strip()}"
        )
    data = json.loads(res.stdout)
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    return MediaProbe(
        path=path,
        duration=float(fmt.get("duration") or 0.0),
        width=int(video[0].get("width") or 0) if video else None,
        height=int(video[0].get("height") or 0) if video else None,
        codec_audio=audio[0].get("codec_name") if audio else None,
        codec_video=video[0].get("codec_name") if video else None,
        has_video=bool(video),
        size_bytes=int(fmt.get("size") or 0),
    )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 do arquivo (checksum de integridade)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_size(path: Path) -> int:
    return path.stat().st_size
