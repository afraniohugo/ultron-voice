import asyncio
import json

from ultron_voice import mcp as active_mcp
from ultron_voice import native_mcp, native_service


def test_native_tools_are_registered_on_the_existing_mcp():
    tools = asyncio.run(active_mcp.server.list_tools())
    names = [tool.name for tool in tools]
    assert names.count("native_voice_health") == 1
    assert names.count("native_list_voices") == 1
    assert names.count("native_generate_speech") == 1


def test_native_health_and_list_are_read_only(monkeypatch):
    monkeypatch.setattr(native_service, "native_list", lambda: {"verified": 10})
    monkeypatch.setattr(native_mcp, "game_active", lambda: False)

    health = json.loads(asyncio.run(native_mcp.native_voice_health()))
    profiles = json.loads(asyncio.run(native_mcp.native_list_voices()))

    assert health == {
        "scope": "laboratory_only",
        "production_enabled": False,
        "verified": 10,
        "game_active": False,
    }
    assert profiles["verified"] == 10


def test_native_generate_forwards_lab_confirmation(monkeypatch):
    seen = {}

    def fake_synthesize(text, profile_id, *, confirm_lab=False):
        seen.update(text=text, profile_id=profile_id, confirm_lab=confirm_lab)
        return {"status": "DRAFT_REVIEW_REQUIRED", "production_enabled": False}

    monkeypatch.setattr(native_service, "native_synthesize", fake_synthesize)
    result = json.loads(asyncio.run(
        native_mcp.native_generate_speech(
            "teste", "qwen3-serena", confirm_lab=True
        )
    ))

    assert result["status"] == "DRAFT_REVIEW_REQUIRED"
    assert seen == {
        "text": "teste",
        "profile_id": "qwen3-serena",
        "confirm_lab": True,
    }
