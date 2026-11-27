"""Engine catalogue: translation and TTS engines available locally."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Engine:
    name: str
    kind: str
    description: str
    config: dict = field(default_factory=dict)


TRANSLATION_ENGINES: dict[str, Engine] = {
    "ollama": Engine(
        name="ollama",
        kind="translate",
        description=(
            "Traduction locale via Ollama (modello argos-multilingual)."
        ),
    ),
    "argos": Engine(
        name="argos",
        kind="translate",
        description="Traduction locale via Argos (argosrt).",
    ),
}

TTS_ENGINES: dict[str, Engine] = {
    "piper": Engine(
        name="piper",
        kind="tts",
        description="TTS local via Piper (CLI).",
    ),
    "espeak": Engine(
        name="espeak",
        kind="tts",
        description="TTS local via Espeak (CLI).",
    ),
    "sapi": Engine(
        name="sapi", kind="tts",
        description="Windows SAPI / System.Speech, CPU only; lab quality not approved.",
    ),
    "qwen3": Engine(
        name="qwen3", kind="tts",
        description="Qwen3-TTS 0.6B CustomVoice, local weights and isolated CPU runtime; lab gate.",
    ),
}


def translation_engines() -> list[Engine]:
    return list(TRANSLATION_ENGINES.values())


def tts_engines() -> list[Engine]:
    return list(TTS_ENGINES.values())


# Canonical names used by the CLI and the MCP server.
list_translation_engines = translation_engines
list_tts_engines = tts_engines


def find_engine(kind: str, name: str) -> Engine | None:
    registry = TRANSLATION_ENGINES if kind == "translate" else TTS_ENGINES
    return registry.get(name)
