"""Ultron Voice — servidor MCP (stdio e SSE).

Interface padrao para agentes: generate_speech, clone_voice, transcribe,
describe_voice, design_voice, list_voices, list_personalities,
list_languages e check_health. Nenhum audio entra no contexto do agente
exceto no modo resources (wav base64 inline, para usos restritos).
"""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

server = FastMCP("ultron-voice")


@server.tool()
async def generate_speech(text: str, profile_id: str | None = None) -> str:
    """Renders a short voice clip from text (engine bound to the agent)."""
    return "Ultron Voice: generate_speech nao implementada neste milestone."


@server.tool()
async def clone_voice(ref_audio_path: str) -> str:
    """Reference audio -> new local voice profile."""
    return "Ultron Voice: clone_voice nao implementada neste milestone."


@server.tool()
async def transcribe(audio_path: str, language: str = "pt", engine: str = "vosk") -> str:
    """Audio -> texto (ASR local)."""
    return await asyncio.to_thread(
        _run, audio_path, language=language, engine=engine, progress=None)


async def _run(audio_path: str, *, language: str, engine: str, progress):
    from backend.engine.asr import transcribe as _transcribe
    return _transcribe(audio_path, language=language, engine=engine, progress=progress)


@server.tool()
async def describe_voice(description: str) -> str:
    """Free text -> voice design attributes (no save)."""
    return "Ultron Voice: describe_voice nao implementada neste milestone."


@server.tool()
async def design_voice(description: str) -> str:
    """Creates a design profile from a description and saves it."""
    return "Ultron Voice: design_voice nao implementada neste milestone."


@server.tool()
async def list_voices() -> str:
    """Enumerate saved voice profiles."""
    return "Ultron Voice: list_voices nao implementada neste milestone."


@server.tool()
async def list_personalities() -> str:
    """Predefined voice personalities."""
    return "Ultron Voice: list_personalities nao implementada neste milestone."


@server.tool()
async def list_languages() -> str:
    """TTS languages enabled for the current engine."""
    return "Ultron Voice: list_languages nao implementada neste milestone."


@server.tool()
async def check_health() -> str:
    """Host + GPU + engine readiness."""
    from ultron_voice.core import health as h
    return str(h.check_health())


def main() -> None:
    import asyncio
    from mcp.server import TransportType

    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
