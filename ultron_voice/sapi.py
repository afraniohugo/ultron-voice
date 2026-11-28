"""Experimental Windows SAPI TTS adapter. Never a human-quality approval.

Uses built-in Microsoft System.Speech without VoiceStudio, internet, APIs,
installed external TTS models, or GPU. This is a lab voice only.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import wave
from pathlib import Path

from .gameguard import game_active


class SapiTTS:
    """A SAPI voice must be selected by its exact local Windows name."""

    def synthesize(self, text: str, out_path: Path, config) -> Path:
        if os.name != "nt":
            raise RuntimeError("SAPI_WINDOWS_ONLY")
        if not isinstance(text, str) or not text.strip() or len(text) > 5000:
            raise ValueError("SAPI_INVALID_TEXT")
        voice = config.model
        if (not isinstance(voice, str) or len(voice) > 100 or
                voice in {"", "pt_BR-polyglot-medium"}):
            raise ValueError("SAPI_VOICE_REQUIRED: specify an installed Windows voice")
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE: voice jobs paused during game")
        output = Path(out_path)
        if output.suffix.lower() != ".wav":
            raise ValueError("SAPI_WAV_ONLY")
        output.parent.mkdir(parents=True, exist_ok=True)
        script = Path(__file__).with_name("sapi_worker.ps1")
        if not script.is_file():
            raise RuntimeError("SAPI_WORKER_MISSING")
        with tempfile.TemporaryDirectory(prefix="uv_sapi_", dir=output.parent) as tmp:
            source = Path(tmp) / "text.txt"
            temp_wav = Path(tmp) / "draft.wav"
            source.write_text(text, encoding="utf-8")
            command = [
                "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                # Per-process only: never changes machine/user execution policy.
                # Required on hosts where local .ps1 scripts are blocked by policy.
                "-ExecutionPolicy", "Bypass", "-File", str(script),
                "-TextPath", str(source), "-OutPath", str(temp_wav),
                "-VoiceName", voice, "-Language", "pt-BR",
            ]
            try:
                result = subprocess.run(
                    command, stdin=subprocess.DEVNULL, capture_output=True,
                    text=True, errors="replace", timeout=85,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("SAPI_TIMEOUT") from exc
            except OSError as exc:
                raise RuntimeError("SAPI_POWERSHELL_UNAVAILABLE") from exc
            if result.returncode != 0:
                # Powershell messages can include paths / original data; do not echo stderr.
                raise RuntimeError("SAPI_ENGINE_FAILED")
            if not temp_wav.is_file() or temp_wav.stat().st_size < 80:
                raise RuntimeError("SAPI_EMPTY_OUTPUT")
            with wave.open(str(temp_wav), "rb") as wav:
                if wav.getnframes() == 0 or wav.getcomptype() != "NONE":
                    raise RuntimeError("SAPI_INVALID_WAV")
            os.replace(temp_wav, output)
        return output
