"""Optional OpenAI Whisper ASR; only explicitly provisioned local weights."""
from __future__ import annotations
from pathlib import Path
from .base import ASREngine
from . import register

MODEL_SIZE = "tiny"

@register("whisper")
class WhisperEngine(ASREngine):
    kind = "whisper"

    def __init__(self, model=None, models_dir=None):
        self._model_dir = Path(models_dir).expanduser() if models_dir else Path.home() / ".cache" / "whisper"
        self._model_path = Path(model).expanduser() if model else self._model_dir / (MODEL_SIZE + ".pt")

    @property
    def name(self):
        return "openai-whisper"

    @property
    def model_dir(self):
        return str(self._model_dir)

    def transcribe(self, audio_path, *, language="pt", progress=None):
        from ultron_voice.gameguard import game_active
        from .vosk_engine import VoskEngine
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        if self._model_path.suffix.lower() != ".pt" or not self._model_path.is_file():
            raise RuntimeError("WHISPER_LOCAL_WEIGHTS_REQUIRED")
        # Never call load_model with a model name (which downloads weights).
        import whisper
        import numpy as np
        pcm, rate = VoskEngine()._read_pcm(audio_path)
        if rate != 16000 or not pcm:
            raise ValueError("WHISPER_INVALID_PCM")
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        model = whisper.load_model(str(self._model_path.resolve()), device="cpu")
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        if progress:
            progress("Transcrevendo com Whisper local")
        result = model.transcribe(np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0,
                                  language=language or None, fp16=False)
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        return (result.get("text") or "").strip()
