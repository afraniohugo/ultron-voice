"""Ultron Voice -- dublagem de video, audiobook e CLI/integracao/QA.

Stack: FFmpeg 9.0.1, ffmpeg-python, pydub, pedalboard (opcional),
Ollama/Argos (traducao local), TTS local (Piper).

Nao publicar. Nao enviar credenciais.
"""

from . import core as core
from . import dub as dub
from . import audiobook as audiobook

__version__ = "0.1.0"

__all__ = ["core", "dub", "audiobook", "__version__"]
