"""Health probes: ffmpeg, ffprobe, Ollama, Argos, Piper, Espeak."""

from __future__ import annotations

import shutil
import subprocess
import urllib.request
from typing import Any


def _which(name: str) -> str | None:
    return shutil.which(name)


def probe_ffmpeg() -> dict[str, Any]:
    binary = _which("ffmpeg")
    return {"ok": bool(binary), "binary": binary or "not found in PATH"}


def probe_ffprobe() -> dict[str, Any]:
    binary = _which("ffprobe")
    return {"ok": bool(binary), "binary": binary or "not found in PATH"}


def probe_ollama() -> dict[str, Any]:
    binary = _which("ollama")
    if not binary:
        return {"ok": False, "binary": None, "reason": "ollama binary not found"}
    try:
        with urllib.request.urlopen(
            "http://localhost:11434/api/tags", timeout=2
        ) as resp:
            return {"ok": resp.status == 200, "server": "localhost:11434"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "server": "localhost:11434", "reason": str(exc)}


def probe_translators() -> dict[str, Any]:
    return {"ollama": probe_ollama(), "argos": {"ok": _which("argosrt") is not None}}


def probe_tts() -> dict[str, Any]:
    return {
        "piper": {"ok": _which("piper") is not None},
        "espeak": {"ok": _which("espeak") is not None},
    }


def check_health() -> dict[str, Any]:
    """Full environment health check for the dub/audiobook pipeline."""
    return {
        "ffmpeg": probe_ffmpeg(),
        "ffprobe": probe_ffprobe(),
        "ollama": probe_ollama(),
        "argos": probe_translators()["argos"],
        "tts": probe_tts(),
    }
