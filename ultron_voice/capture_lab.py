"""Opt-in DirectShow capture candidate; never invoked automatically or by MCP.

Capture is bounded and returns PCM in memory, without saving microphone audio.
Hardware acceptance is separate from the inert subprocess tests.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .audio_turns import audio_turns, AudioTurnError
from .gameguard import game_active


def _command(device, seconds):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioTurnError("FFMPEG_REQUIRED")
    return [str(Path(ffmpeg).resolve()), "-hide_banner", "-nostdin", "-v", "error",
            "-f", "dshow", "-i", "audio=" + device, "-t", str(seconds),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            "-f", "s16le", "pipe:1"]


def capture_pcm(device, *, seconds=5, consent=False, cancel=None):
    """Capture only the explicit selected device, after explicit local consent."""
    if consent is not True:
        raise AudioTurnError("AUDIO_EXPLICIT_CONSENT_REQUIRED")
    if (not isinstance(device, str) or not device.strip() or len(device) > 200
            or device.casefold().strip() in ("default", "auto", "none")
            or any(ord(c) < 32 or c in ':="\\' for c in device)):
        raise AudioTurnError("AUDIO_EXPLICIT_DEVICE_REQUIRED")
    if type(seconds) is not int or not 1 <= seconds <= 30:
        raise ValueError("AUDIO_CAPTURE_LIMIT")
    cancel = cancel if cancel is not None else threading.Event()
    if cancel.is_set():
        raise AudioTurnError("AUDIO_CANCELLED")
    with audio_turns.lease("capture", consent=True):
        if cancel.is_set():
            raise AudioTurnError("AUDIO_CANCELLED")
        proc = subprocess.Popen(_command(device, seconds), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        deadline = time.monotonic() + seconds + 8
        guard_at = time.monotonic() + 1
        try:
            while True:
                if cancel.is_set():
                    raise AudioTurnError("AUDIO_CANCELLED")
                now = time.monotonic()
                if now >= deadline:
                    raise AudioTurnError("AUDIO_CAPTURE_TIMEOUT")
                if now >= guard_at:
                    if game_active():
                        raise AudioTurnError("GAMEGUARD_ACTIVE")
                    guard_at = time.monotonic() + 1
                try:
                    pcm, _ = proc.communicate(timeout=min(0.2, deadline-now))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if cancel.is_set():
                raise AudioTurnError("AUDIO_CANCELLED")
            if game_active():
                raise AudioTurnError("GAMEGUARD_ACTIVE")
            if proc.returncode != 0:
                raise AudioTurnError("AUDIO_CAPTURE_FAILED")
            if not pcm or len(pcm) % 2 or len(pcm) > seconds * 32000:
                raise AudioTurnError("AUDIO_INVALID_PCM")
            return pcm
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
            if proc.stdout is not None:
                proc.stdout.close()
