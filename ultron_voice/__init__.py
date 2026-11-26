"""Ultron Voice -- dublagem de video, audiobook e CLI/integracao/QA.

Stack: FFmpeg 9.0.1, ffmpeg-python, pydub, pedalboard (opcional),
Ollama/Argos (traducao local), TTS local (Piper).

Nao publicar. Nao enviar credenciais.
"""

from importlib import import_module


def __getattr__(name):
    if name in ("core", "dub", "audiobook"):
        module = import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__version__ = "0.1.0"

__all__ = ["core", "dub", "audiobook", "__version__"]
