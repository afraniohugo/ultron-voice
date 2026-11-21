"""Motor ASR vosk (CPU-only, leve, nao exige torch).

Requisitos:
    uv sync -e ".[asr]"

Modelos disponiveis (baixados automaticamente na primeira usos):
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
import zipfile
from pathlib import Path

from .base import ASREngine
from . import register

logger = logging.getLogger(__name__)

# Modelos do vosk disponiveis. Chave = idioma (corte do motor).
MODEL_ZIP = {
    "pt": "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip",
    "en": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
}
MODEL_NAME = {
    "pt": "vosk-model-small-pt-0.3",
    "en": "vosk-model-small-en-us-0.15",
}

# Diretorio padrao para guardar os modelos de ASR.
_DEFAULT_models_DIR = Path(
    os.environ.get("ULTRON_VOICE_MODELS_DIR", str(Path.home() / ".ultron-voice" / "models"))
).expanduser()
try:
    _DEFAULT_models_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass


class VoskUnavailable(RuntimeError):
    """O motor vosk nao esta instalado ou nao tem modelo baixado."""


@register("vosk")
class VoskEngine(ASREngine):
    """Transcricao com vosk (modelo pequeno, roda em CPU)."""

    kind = "vosk"

    def __init__(self, model=None, models_dir=None):
        self.model_path = None
        self._model = None
        self._model_dir = self._resolve_model_dir(model, models_dir)

    def _resolve_model_dir(self, model, models_dir):
        base = Path(models_dir) if models_dir else _DEFAULT_models_DIR
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if model:
            candidate = Path(model)
            if candidate.exists() and candidate.is_dir():
                return candidate
        return base

    def _ensure_model(self, language):
        """Garante que o modelo do idioma informado esta instalado."""
        language = (language or "pt").lower()
        if language not in MODEL_NAME:
            raise ValueError(
                f"Motor vosk nao suporta idioma: {language!r}. Use pt ou en."
            )
        name = MODEL_NAME[language]
        target = self._model_dir / name
        zip_path = target.with_name(target.name + ".zip")

        if target.is_dir() and (
            (target / "final.mdl").exists()
            or any((target / d).is_dir() for d in ("am", "graph", "ivector"))
            or (target / "conf").is_file()
        ):
            return target
        if zip_path.exists():
            self._extract(zip_path, self._model_dir)
            if not (target / "final.mdl").exists():
                raise FileNotFoundError(f"Modelo extraido sem 'am': {target}")
            return target

        self._download(MODEL_ZIP[language], zip_path)
        self._extract(zip_path, self._model_dir)
        if not (target / "final.mdl").exists():
            raise FileNotFoundError(f"Modelo baixado/extrado sem 'am': {target}")
        return target

    def _download(self, url, dest):
        import urllib.request

        logger.info("Baixando modelo ASR (%s) -> %s", self.kind, dest)
        req = urllib.request.Request(url, headers={"User-Agent": "UltronVoice/1.0"})
        if dest.exists():
            dest.unlink()
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

    def _extract(self, zip_path, dest):
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)

    def _read_pcm(self, audio_path):
        """Return (pcm_bytes, sample_rate) com audio normalizado para 16kHz mono s16le.

        Usa o wave nativo. Se o audio nao for 16kHz mono s16le, normaliza via ffmpeg.
        """
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
                ffmpeg, "-y", "-v", "error", "-i", audio_path,
                "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", "-f", "s16le", tmp,
            ]
            subprocess.run(cmd, check=True)
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

        model_dir = self._ensure_model(language)
        if progress:
            progress(f"Carregando modelo vosk ({model_dir.name}) ...")

        # import otimista: carrega somente quando necessario (nao impede
        # import do modulo se o vosk nao estiver instalado).
        from vosk import Model, KaldiRecognizer

        model = Model(str(model_dir))
        self._model = model
        pcm, sr = self._read_pcm(audio_path)
        if sr != 16000:
            raise ValueError(
                f"taxa de amostragem inesperada ({sr}). O motor vosk exige 16kHz mono."
            )
        if progress:
            progress(f"Transcreveendo com vosk: {audio_path} ...")

        recognizer = KaldiRecognizer(model, 16000)
        chunks = []
        # feed em blocos de 1s (16000 amostras x 2 bytes = 32000 bytes)
        step = 16000 * 2
        for offset in range(0, len(pcm), step):
            if recognizer.AcceptWaveform(pcm[offset:offset + step]):
                text = json.loads(recognizer.Result()).get("text", "")
                if text:
                    chunks.append(text)
        tail = json.loads(recognizer.FinalResult()).get("text", "")
        if tail:
            chunks.append(tail)
        return " ".join(chunks).strip()

    @property
    def name(self):
        return "vosk"

    @property
    def model_dir(self):
        return str(self._model_dir)
