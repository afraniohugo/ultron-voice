"""Motor ASR openai-whisper (torch).

Motor complementar. Mais pesado e exige torch. Nao e o caminho escolhido
para rodar no hardware padrao (CPU comum); e mantido como opcao de maior
qualidade.

Requisitos de validacao completa:
    uv sync -e ".[asr]"      # openai-whisper + vosk (sem torch)
    uv sync -e ".[local]"    # torch + transformers + openai-whisper

Para testar o whisper, instale a variante torch: uv sync -e ".[local]"
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import ASREngine
from . import register

logger = logging.getLogger(__name__)

try:
    import whisper  # noqa: F401
except Exception:  # pragma: no cover - importa OK somente se torch+openai-whisper estao
    whisper = None

# Tamanho do modelo whisper. 'tiny' e o mais leve (rapido, qualidade
# aceitavel para validacao). Use 'base'/'small' se houver recursos.
MODEL_SIZE = "tiny"


@register("whisper")
class WhisperEngine(ASREngine):
    """Transcricao com openai-whisper (torch)."""

    kind = "whisper"

    def __init__(self, model=None, models_dir=None):
        self.model_size = MODEL_SIZE
        self._model = None

    @property
    def name(self):
        return "openai-whisper"

    @property
    def model_dir(self):
        # Whisper guarda os pesos no cache do huggingface por padrao.
        return str(Path.home() / ".cache" / "whisper")

    def transcribe(self, audio_path, *, language="pt", progress=None):
        if whisper is None:
            raise RuntimeError(
                "Motor whisper nao disponivel. Instale torch + openai-whisper "
                "(ex.: uv sync -e \".[asr]\" + \".[local]\")."
            )
        import whisper as _w

        try:
            model = _w.load_model(self.model_size)
        except Exception as exc:
            raise RuntimeError(
                f"nao foi possivel carregar o modelo whisper ({exc})."
            ) from exc
        self._model = model
        if progress:
            progress(f"Transcreveendo com whisper ({self.model_size}) ...")

        try:
            result = model.transcribe(
                audio_path,
                language=language or None,  # None = desconhecido (multilingua)
                fp16=False,                 # CPU: desabilita FP16 (preciso)
            )
        finally:
            del model

        return (result.get("text") or "").strip()

    @property
    def model_dir(self):
        return str(Path.home() / ".cache" / "whisper")
