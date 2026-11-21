"""Ultron Voice — TTS local (engine package).

Voz sintetica 100% local. Backends CLI (piper / espeak); entrada de texto
e saida de wave sem servicos remotos.
"""

from __future__ import annotations

from .tts import *  # noqa: F401

__all__ = ["TTS", "PiperTTS", "EspeakTTS", "TTSConfig", "build_tts"]
