"""Motor ASR vosk (CPU-only, leve, nao exige torch).

Requisitos:
    uv sync -e ".[asr]"

Modelos locais (provisionamento separado; nunca baixar durante ASR):
    pt -> vosk-model-small-pt-0.3  (portugues do Brasil)
    en -> vosk-model-small-en-us-0.15  (ingles)

Armazenamento padrao dos modelos:
    <home>/.ultron-voice/models
    (sobrescreve com a variavel de ambiente ULTRON_VOICE_MODELS_DIR)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import wave
import threading
import time
from pathlib import Path

from .base import ASREngine
from . import register

logger = logging.getLogger(__name__)

# Modelos do vosk disponiveis. Chave = idioma (corte do motor).
MODEL_NAME = {
    "pt": "vosk-model-small-pt-0.3",
    "en": "vosk-model-small-en-us-0.15",
}

# Diretorio padrao para guardar os modelos de ASR.
_DEFAULT_models_DIR = Path(
    os.environ.get("ULTRON_VOICE_MODELS_DIR", str(Path.home() / ".ultron-voice" / "models"))
).expanduser()


class VoskUnavailable(RuntimeError):
    """O motor vosk nao esta instalado ou nao tem modelo baixado."""


@register("vosk")
class VoskEngine(ASREngine):
    """Transcricao com vosk (modelo pequeno, roda em CPU)."""

    kind = "vosk"

    def __init__(self, model=None, models_dir=None):
        self.model_path = None
        self._model = None
        self._model_lock = threading.Lock()
        self._explicit_model = Path(model).expanduser() if model else None
        self._model_dir = Path(models_dir).expanduser() if models_dir else _DEFAULT_models_DIR

    @staticmethod
    def _valid_model(target):
        return target.is_dir() and (
            (target / "final.mdl").is_file()
            or (target / "am" / "final.mdl").is_file()
        )

    def _ensure_model(self, language):
        """Only use a provisioned local model; never download or extract."""
        language = (language or "pt").lower()
        if language not in MODEL_NAME:
            raise ValueError("VOSK_LANGUAGE_UNSUPPORTED")
        target = self._explicit_model or self._model_dir / MODEL_NAME[language]
        if not self._valid_model(target):
            raise VoskUnavailable("VOSK_LOCAL_MODEL_REQUIRED")
        return target.resolve()

    def _load_model(self, language):
        from vosk import Model
        target = self._ensure_model(language)
        with self._model_lock:
            if self._model is None or self.model_path != target:
                self._model = Model(str(target))
                self.model_path = target
            return self._model

    def transcribe_stream(self, pcm_chunks, *, language="pt", sample_rate=16000):
        """Yield partial/final segment events from caller-supplied PCM16 mono.

        Each chunk is at most one second. No capture, network or whole-stream
        buffering. Final events contain segments, not cumulative text.
        """
        from vosk import KaldiRecognizer
        from ultron_voice.gameguard import game_active
        if sample_rate != 16000:
            raise ValueError("VOSK_PCM_RATE_REQUIRED")
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        recognizer = KaldiRecognizer(self._load_model(language), 16000)
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        last_partial = ""
        next_guard = time.monotonic() + 1
        for pcm in pcm_chunks:
            if time.monotonic() >= next_guard:
                if game_active():
                    raise RuntimeError("GAMEGUARD_ACTIVE")
                next_guard = time.monotonic() + 1
            if not isinstance(pcm, bytes) or not pcm or len(pcm) > 32000 or len(pcm) % 2:
                raise ValueError("VOSK_INVALID_PCM_CHUNK")
            if recognizer.AcceptWaveform(pcm):
                text = json.loads(recognizer.Result()).get("text", "")
                last_partial = ""
                if text:
                    yield {"type": "final", "text": text}
            else:
                partial = json.loads(recognizer.PartialResult()).get("partial", "")
                if partial and partial != last_partial:
                    last_partial = partial
                    yield {"type": "partial", "text": partial}
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        tail = json.loads(recognizer.FinalResult()).get("text", "")
        if tail:
            yield {"type": "final", "text": tail}

    def _read_pcm(self, audio_path):
        """Return (pcm_bytes, sample_rate) com audio normalizado para 16kHz mono s16le.

        Usa o wave nativo. Se o audio nao for 16kHz mono s16le, normaliza via ffmpeg.
        """
        audio_path = str(Path(audio_path).resolve(strict=True))
        if not Path(audio_path).is_file():
            raise ValueError("VOSK_LOCAL_AUDIO_REQUIRED")
        try:
            with wave.open(audio_path, "rb") as wf:
                if wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 16000:
                    return wf.readframes(wf.getnframes()), wf.getframerate()
        except wave.Error:
            pass

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                "ffmpeg nao encontrado no PATH. Instale o ffmpeg e repita."
            )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tmp = tf.name
        try:
            cmd = [
                ffmpeg, "-nostdin", "-y", "-v", "error", "-protocol_whitelist", "file,pipe", "-i", audio_path,
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", tmp,
            ]
            subprocess.run(cmd, check=True, timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            with wave.open(tmp, "rb") as wf:
                return wf.readframes(wf.getnframes()), wf.getframerate()
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def transcribe(self, audio_path, *, language="pt", progress=None):
        """Transcreve audio em texto (pt ou en), via vosk."""
        language = (language or "pt").lower()
        if language not in MODEL_NAME:
            raise ValueError(
                f"Motor vosk nao suporta idioma: {language!r}. Use pt ou en."
            )

        from ultron_voice.gameguard import game_active
        if game_active():
            raise RuntimeError("GAMEGUARD_ACTIVE")
        self._ensure_model(language)
        pcm, sr = self._read_pcm(audio_path)
        if progress:
            progress("Transcrevendo com Vosk local")
        events = self.transcribe_stream(
            (pcm[offset:offset + 6400] for offset in range(0, len(pcm), 6400)),
            language=language, sample_rate=sr,
        )
        return " ".join(event["text"] for event in events
                        if event["type"] == "final").strip()

    @property
    def name(self):
        return "vosk"

    @property
    def model_dir(self):
        return str(self._model_dir)
