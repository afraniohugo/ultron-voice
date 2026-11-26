"""Lab-only native voice tools for the single existing Ultron Voice MCP."""
from __future__ import annotations

import asyncio
import json

from . import native_service
from .gameguard import game_active


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


async def native_voice_health() -> str:
    """Read native readiness without loading a model or contacting VoiceStudio."""
    data = await asyncio.to_thread(native_service.native_list)
    active = await asyncio.to_thread(game_active)
    return _dump({
        "scope": "laboratory_only",
        "production_enabled": False,
        "verified": data["verified"],
        "game_active": active,
    })


async def native_list_voices() -> str:
    """List local voice profiles and hash-verified lab samples."""
    return _dump(await asyncio.to_thread(native_service.native_list))


async def native_generate_speech(
    text: str,
    profile_id: str,
    confirm_lab: bool = False,
) -> str:
    """Generate a local lab draft only; requires explicit lab confirmation."""
    result = await asyncio.to_thread(
        native_service.native_synthesize,
        text,
        profile_id,
        confirm_lab=confirm_lab,
    )
    return _dump(result)
