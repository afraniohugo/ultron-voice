"""Ultron Voice - motor ASR (subpacote do engine).

API publica do motor de transcricao local. Todos os motores rodam 100% local.

Uso:
    from backend.engine.asr import transcribe, create_engine

    text = transcribe("consulta.wav", language="pt")      # texto transcrito
    engine = create_engine("vosk", model="vosk-model-small-pt-BR-0.22")
"""

from __future__ import annotations

from pathlib import Path

from .base import ASREngine

__all__ = ["transcribe", "create_engine", "ASREngine", "DEFAULT_ENGINE", "DEFAULT_LANGUAGE"]

# Motor padrao: vosk (leve, CPU-only, nao exige torch, Python 3.14).
DEFAULT_ENGINE = "vosk"
DEFAULT_LANGUAGE = "pt"

# Registro de motores (preenchido pelos modulos de motor na importacao).
_REGISTRY: dict[str, type] = {}


def register(kind):
    """Registrar um motor ASR. Uso: @register("vosk")"""
    def _deco(cls):
        _REGISTRY[kind] = cls
        return cls
    return _deco


def create_engine(kind, model=None, models_dir=None):
    """Cria uma instancia de motor ASR registrado."""
    factory = _REGISTRY.get(kind)
    if factory is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Motor ASR desconhecido: {kind!r}. Escolha entre: {available}.")
    if models_dir is not None:
        models_dir = Path(models_dir)
    return factory(model=model, models_dir=models_dir)


def transcribe(audio_path, *, language="pt", engine="vosk", model=None,
               models_dir=None, progress=None):
    """Audio -> texto. Usa o motor indicado (default: vosk).

    Args:
        audio_path: caminho do arquivo de audio (wav/mp3/ogg, etc.).
        language: idioma de entrada. "pt"=portugues do Brasil, "en"=ingles.
        engine: motor a usar. "vosk" (padrao) ou "whisper".
        model: (opcional) caminho/identificador do modelo do motor.
        models_dir: (opcional) diretorio onde ficam os modelos.
        progress: callable(opcao) para logs opcionais.

    Returns:
        Texto transcrito. Se falhar, retorna uma string com marcador 'ERR:'.
    """
    if not Path(audio_path).is_absolute():
        audio_path = str(Path.cwd() / audio_path)
    if not Path(audio_path).exists():
        raise FileNotFoundError(f"Arquivo de audio nao encontrado: {audio_path!r}")

    language = (language or "pt").lower()
    engine_instance = create_engine(engine, model=model, models_dir=models_dir)
    try:
        return engine_instance.transcribe(audio_path, language=language, progress=progress)
    except Exception as exc:  # mapeia a falha em uma string de erro clara
        msg = f"ERR:{engine}:{type(exc).__name__}:{exc}"
        if progress is not None:
            progress(msg)
        return msg

# Registrar motores ao importar este subpacote (sozinhos, na inicializacao).
from . import vosk_engine  # noqa: F401  # registrar 'vosk'
from . import whisper_engine  # noqa: F401  # registrar 'whisper'
