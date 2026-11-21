"""Local translation: argos (argos-translate CLI) or Ollama.

Both backends are optional. When a backend is unavailable the pipeline fails
fast with a clear error instead of silently falling back to an external API.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

try:  # optional
    import ollama  # type: ignore
except ImportError:  # pragma: no cover - ollama is optional
    ollama = None


@dataclass(frozen=True)
class TranslateConfig:
    engine: str = "ollama"
    source_lang: str = "pt-BR"
    target_lang: str = "en-US"
    model: str = "argo/argos-multilingual"
    prompt: str = "Traduza apenas para o ingles, texto simples."


class Translator:
    """Translate one text into the target language (offline)."""

    def translate(self, text: str, config: TranslateConfig) -> str:
        raise NotImplementedError


class ArgosTranslator(Translator):
    def translate(self, text: str, config: TranslateConfig) -> str:
        exe = "argos-translate"
        res = subprocess.run(
            [exe, "--source-lang", config.source_lang,
             "--target-lang", config.target_lang, text],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(f"argos-translate falhou: {res.stderr}")
        return res.stdout.strip()


class OllamaTranslator(Translator):
    def translate(self, text: str, config: TranslateConfig) -> str:
        if ollama is None:
            raise RuntimeError("ollama nao instalado. pip install ollama")
        prompt = config.prompt or f"Translate only to {config.target_lang}, plain text:"
        response = ollama.generate(
            model=config.model, prompt=prompt, keep_alive=-1
        )
        return response["response"].strip()


def build_translator(config: TranslateConfig) -> Translator:
    if config.engine == "argos":
        return ArgosTranslator()
    return OllamaTranslator()
