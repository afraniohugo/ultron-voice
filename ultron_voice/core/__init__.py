"""Ultron Voice core: catalogue, health, models e registry/history."""

from .catalogue import Engine, list_translation_engines, list_tts_engines
from .health import check_health, probe_ollama, probe_translators
from .models import Checksums, JobStatus
from .registry import Registry
def __getattr__(name):
    if name == "DubJob":
        from ..dub import DubJob
        return DubJob
    if name == "AudiobookJob":
        from ..audiobook import AudiobookJob
        return AudiobookJob
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Engine",
    "JobStatus",
    "Checksums",
    "DubJob",
    "AudiobookJob",
    "Registry",
    "list_translation_engines",
    "list_tts_engines",
    "check_health",
    "probe_ollama",
    "probe_translators",
]
