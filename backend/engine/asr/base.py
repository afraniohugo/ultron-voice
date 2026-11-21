"""Interface base dos motores ASR.

Todos os motores extendem ASREngine e implementam transcribe().
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ASREngine(ABC):
    """Interface minima de um motor de transcricao local."""

    kind: str  # identifica o motor, ex: "vosk" | "whisper"

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome amigavel do motor."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_dir(self) -> str:
        """Diretorio onde o modelo atual esta instalado."""
        raise NotImplementedError

    @abstractmethod
    def transcribe(self, audio_path: str, *, language: str = "pt",
                   progress=None) -> str:
        """Transcreve um arquivo de audio em texto.

        Args:
            audio_path: caminho do audio.
            language: idioma ("pt" ou "en").

        Returns:
            Texto transcrito. Retorna string vazia se nao houver fala
            confidente ou se o audio estiver vazio.
        """
        raise NotImplementedError
