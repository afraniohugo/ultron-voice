"""Ultron Voice - motor de transcricao local (ASR).

Interface unica de entrada e o registry de motores.
Todos os motores rodam 100% local, sem servicos remotos, sem segredos.

Estrategia escolhida: **vosk** (leve, CPU-only, nao exige torch e roda
direto em Python 3.14). Ventilador complementar: **openai-whisper**
(qualidade maior, mas exige torch, mais pesado e demora mais para iniciar).

Estrutura:
    backend/engine/
    backend/engine/asr/
        __init__.py            # API publica
        base.py                # interface ASREngine
        vosk_engine.py         # motor vosk (principal, validado)
        whisper_engine.py      # motor openai-whisper (complementar)
        README.md              # documentacao do motor

Instalacao:
    uv sync -e ".[asr]"

Uso direto:
    uv run python -c "from backend.engine.asr import transcribe; print(transcribe('a.wav', language='pt'))"
"""

from __future__ import annotations

from .asr import ASREngine, create_engine, transcribe  # noqa: F401

__all__ = ["transcribe", "create_engine", "ASREngine", "DEFAULT_ENGINE", "DEFAULT_LANGUAGE"]

# Motor padrao: vosk (leve, CPU-only, nao exige torch, Python 3.14).
DEFAULT_ENGINE = "vosk"
DEFAULT_LANGUAGE = "pt"
