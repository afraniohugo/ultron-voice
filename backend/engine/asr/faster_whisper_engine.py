"""Offline CTranslate2 Whisper using an explicitly provisioned model directory."""
from pathlib import Path
from .base import ASREngine
from . import register

@register("faster-whisper")
class FasterWhisperEngine(ASREngine):
    kind = "faster-whisper"

    def __init__(self, model=None, models_dir=None):
        self._path = Path(model or models_dir).expanduser() if model or models_dir else None

    @property
    def name(self):
        return "faster-whisper"

    @property
    def model_dir(self):
        return str(self._path) if self._path else ""

    def transcribe(self, audio_path, *, language="pt", progress=None):
        from ultron_voice.gameguard import game_active
        from .vosk_engine import VoskEngine
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        if self._path is None or not self._path.is_dir() or not all(
            (self._path / name).is_file()
            for name in ("config.json", "model.bin", "tokenizer.json")
        ):
            raise RuntimeError("FASTER_WHISPER_LOCAL_WEIGHTS_REQUIRED")
        from faster_whisper import WhisperModel
        import numpy as np
        pcm, rate = VoskEngine()._read_pcm(audio_path)
        if rate != 16000 or not pcm:
            raise ValueError("WHISPER_INVALID_PCM")
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        model = WhisperModel(str(self._path.resolve()), device="cpu",
                             compute_type="int8", cpu_threads=4,
                             num_workers=1, local_files_only=True)
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        if progress:
            progress("Transcrevendo com Faster-Whisper local")
        segments, _ = model.transcribe(
            np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0,
            language=language or None, beam_size=1, vad_filter=False)
        parts = []
        for segment in segments:
            if game_active():
                raise RuntimeError("GAMEGUARD_ACTIVE")
            parts.append(segment.text.strip())
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        return " ".join(part for part in parts if part)
