"""Media probing, checksum and container helpers (FFprobe/FFmpeg).

Also provides WAV/MP3 export utilities for TTS output.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

try:  # optional
    from pydub import AudioSegment
except ImportError:  # pragma: no cover
    AudioSegment = None

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


# ---------------------------------------------------------------------------
# Export Utilities
# ---------------------------------------------------------------------------
def export_wav_to_mp3(wav_path: Path, mp3_path: Path, bitrate: str = "192k") -> Path:
    """Convert WAV to MP3 using FFmpeg.

    Args:
        wav_path: Source WAV file
        mp3_path: Destination MP3 file
        bitrate: MP3 bitrate (e.g., "192k", "128k", "320k")

    Returns:
        Path to the created MP3 file
    """
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-i", str(wav_path),
        "-codec:a", "libmp3lame",
        "-b:a", bitrate,
        "-map_metadata", "0",
        str(mp3_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg WAV->MP3 falhou: {res.stderr.strip()}")
    return mp3_path


def export_wav_to_mp3_pydub(wav_path: Path, mp3_path: Path, bitrate: str = "192k") -> Path:
    """Convert WAV to MP3 using pydub (requires ffmpeg in PATH).

    Fallback when FFmpeg subprocess is not desired.
    """
    if AudioSegment is None:
        raise RuntimeError("pydub não disponível: pip install pydub")
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_wav(str(wav_path))
    audio.export(str(mp3_path), format="mp3", bitrate=bitrate)
    return mp3_path


def export_to_wav(source_path: Path, wav_path: Path, sample_rate: int = 24000,
                  channels: int = 1, sample_width: int = 2) -> Path:
    """Convert any audio file to WAV with specific format.

    Args:
        source_path: Source audio file (any format FFmpeg supports)
        wav_path: Destination WAV file
        sample_rate: Target sample rate (Hz)
        channels: Target channels (1=mono, 2=stereo)
        sample_width: Target sample width in bytes (2=16-bit)

    Returns:
        Path to the created WAV file
    """
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-i", str(source_path),
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-sample_fmt", "s16" if sample_width == 2 else "s32",
        "-acodec", "pcm_s16le" if sample_width == 2 else "pcm_s32le",
        str(wav_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg conversão para WAV falhou: {res.stderr.strip()}")
    return wav_path


def validate_wav(path: Path) -> bool:
    """Validate that a file is a valid WAV with PCM data."""
    try:
        with wave.open(str(path), "rb") as wav:
            if wav.getcomptype() != "NONE":
                return False
            if wav.getnframes() == 0:
                return False
            return True
    except Exception:
        return False


def get_wav_info(path: Path) -> dict:
    """Get detailed WAV file information."""
    with wave.open(str(path), "rb") as wav:
        return {
            "channels": wav.getnchannels(),
            "sample_width": wav.getsampwidth(),
            "frame_rate": wav.getframerate(),
            "n_frames": wav.getnframes(),
            "duration_seconds": wav.getnframes() / wav.getframerate(),
            "compression_type": wav.getcomptype(),
            "compression_name": wav.getcompname(),
        }


def concat_wavs(wav_paths: list[Path], output_path: Path) -> Path:
    """Concatenate multiple WAV files with identical format.

    Args:
        wav_paths: List of WAV files to concatenate (must have same format)
        output_path: Output WAV file

    Returns:
        Path to the concatenated WAV file
    """
    if not wav_paths:
        raise ValueError("nenhum arquivo WAV para concatenar")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(wav_paths[0]), "rb") as first:
        fmt = (first.getnchannels(), first.getsampwidth(),
               first.getframerate(), first.getcomptype())
        if fmt[-1] != "NONE":
            raise ValueError("WAV comprimido não suportado")

    with wave.open(str(output_path), "wb") as dest:
        dest.setnchannels(fmt[0])
        dest.setsampwidth(fmt[1])
        dest.setframerate(fmt[2])

        for src_path in wav_paths:
            with wave.open(str(src_path), "rb") as src:
                src_fmt = (src.getnchannels(), src.getsampwidth(),
                           src.getframerate(), src.getcomptype())
                if src_fmt != fmt:
                    raise ValueError(f"formato WAV incompatível: {src_path}")
                while True:
                    block = src.readframes(4096)
                    if not block:
                        break
                    dest.writeframesraw(block)

    return output_path
