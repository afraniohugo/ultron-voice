"""Ultron Voice MCP: thin, original bridge to installed local VoiceStudio and Studio.

No VoiceStudio source code is included. Every operation is local, review-gated,
and production audio routing is deliberately not enabled.
"""
from __future__ import annotations

import asyncio
import json
from mcp.server.fastmcp import FastMCP
from . import voicestudio_bridge as bridge
from . import native_mcp as native_tools

server = FastMCP("ultron-voice")


def dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


@server.tool()
async def check_health() -> str:
    """MCP/VoiceStudio/Ultron Studio readiness, GameGuard, no side effects."""
    return dump(await asyncio.to_thread(bridge.health))


@server.tool()
async def list_voices() -> str:
    """List the installed VoiceStudio voice profiles; never select a default."""
    return dump(await asyncio.to_thread(bridge.voices))


@server.tool()
async def list_engines() -> str:
    """List installed and configured VoiceStudio engines from its local CLI."""
    return dump(await asyncio.to_thread(bridge.engines))


@server.tool()
async def generate_speech(text: str, profile_id: str | None = None,
                          engine: str | None = None,
                          language: str = "pt", speed: float = 1.0) -> str:
    """Render a short draft WAV into Studio's UNVERIFIED staging area.

    Requires a selected saved voice profile. Cannot publish or bind media.
    Stops if GameGuard detects Warzone. No API paid or remote TTS.
    """
    return dump(await asyncio.to_thread(
        bridge.synthesize, text, profile_id, engine, language, speed))


@server.tool()
async def transcribe(audio_path: str, language: str = "pt") -> str:
    """Local VoiceStudio ASR for existing permitted audio, with review status."""
    return dump(await asyncio.to_thread(
        bridge.speech_to_text, audio_path, language))


@server.tool()
async def describe_voice(description: str) -> str:
    """Describe a possible VoiceStudio voice without saving a new profile."""
    return dump(await asyncio.to_thread(bridge.describe, description))


@server.tool()
async def design_voice(description: str, profile_name: str,
                       confirm_create: bool = False, language: str = "pt") -> str:
    """Design/save a VoiceStudio profile only with explicit create confirmation."""
    return dump(await asyncio.to_thread(
        bridge.design, description, profile_name, confirm_create, language))


@server.tool()
async def clone_voice(ref_audio_path: str, profile_name: str,
                      consent_confirmed: bool = False, language: str = "pt") -> str:
    """Create a lab-only clone only when voice-owner consent is verified.

    VoiceStudio's own consent workflows and commercial rights still apply.
    """
    return dump(await asyncio.to_thread(
        bridge.clone, ref_audio_path, profile_name, consent_confirmed, language))


@server.tool()
async def list_personalities() -> str:
    """Compatibility tool: show actual saved voices; no invented personalities."""
    data = await asyncio.to_thread(bridge.voices)
    data["note"] = "Personality presets depend on existing VoiceStudio profiles."
    return dump(data)


@server.tool()
async def list_languages() -> str:
    """Compatibility tool: engine data is authoritative for supported languages."""
    data = await asyncio.to_thread(bridge.engines)
    data["note"] = "Available languages vary by installed engine and profile."
    return dump(data)


@server.tool()
async def studio_audio_handoff(audio_path: str) -> str:
    """Verify Studio can catalog an Ultron Voice draft without rights or binding."""
    return dump(await asyncio.to_thread(bridge.studio_audio_handoff, audio_path))



@server.tool()
async def start_voice_backend() -> str:
    """Start the installed VoiceStudio backend headlessly (one instance).

    Does not schedule autostart, register a service, or authorize publications.
    """
    return dump(await asyncio.to_thread(bridge.start_backend))


# Register lab-only native tools on this existing MCP server; no second server.
server.tool()(native_tools.native_voice_health)
server.tool()(native_tools.native_list_voices)
server.tool()(native_tools.native_generate_speech)


def main() -> None:
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
