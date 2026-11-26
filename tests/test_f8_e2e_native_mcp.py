"""Isolated F8 contract: native draft to Studio handoff, with no production writes.

The test uses a fake TTS engine, temporary directories and a fake Studio source
catalog. The live local handoff was verified separately against existing drafts.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import wave
from pathlib import Path

import pytest

from ultron_voice import native_mcp, native_service, voicestudio_bridge as bridge


def _write_pcm16(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\\x01\\x00" * 240)


@pytest.fixture
def isolated_studio(monkeypatch, tmp_path):
    audio_root = tmp_path / "studio" / "audio_assets"
    output_root = audio_root / "ultron_voice_drafts"
    output_root.mkdir(parents=True)
    catalog = {"items": [{
        "name": "ultron_voice_f8_e2e_test.wav",
        "id": "e2e-isolated-source-id",
        "scope": "STAGING_UNVERIFIED",
    }]}

    monkeypatch.setattr(bridge, "STUDIO_AUDIO_ROOT", audio_root)
    monkeypatch.setattr(bridge, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(bridge, "INPUT_ROOTS", (audio_root,))
    monkeypatch.setattr(bridge, "_get_json", lambda url: catalog)
    return output_root


def test_e2e_native_tool_to_studio_handoff_is_isolated(
    monkeypatch, tmp_path, isolated_studio
):
    lab_root = tmp_path / "lab"
    manifest = tmp_path / "profile.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(native_service.native_catalog, "LAB_ROOT", lab_root)
    monkeypatch.setattr(
        native_service.native_catalog,
        "resolve_profile",
        lambda profile_id: ("qwen3", manifest),
    )
    monkeypatch.setattr(native_service, "game_active", lambda: False)

    class FakeTTS:
        def synthesize(self, text, destination, config):
            _write_pcm16(destination)

    monkeypatch.setattr(native_service, "build_tts", lambda config: FakeTTS())

    draft = json.loads(asyncio.run(
        native_mcp.native_generate_speech(
            "Teste local isolado.", "qwen3-serena", confirm_lab=True
        )
    ))
    assert draft["status"] == "DRAFT_REVIEW_REQUIRED"
    assert draft["production_enabled"] is False

    staged = isolated_studio / "ultron_voice_f8_e2e_test.wav"
    shutil.copyfile(draft["path"], staged)
    result = bridge.studio_audio_handoff(str(staged))
    assert result["ok"] is True
    assert result["status"] == "STAGING_UNVERIFIED"
    assert result["publication_allowed"] is False
    assert result["audio_binding_allowed"] is False
    assert result["sha256"] == hashlib.sha256(staged.read_bytes()).hexdigest()


def test_e2e_native_tool_rejects_missing_lab_confirmation(monkeypatch):
    monkeypatch.setattr(native_service, "game_active", lambda: False)

    def fail_if_loaded(config):
        raise AssertionError("model must not load without lab confirmation")

    monkeypatch.setattr(native_service, "build_tts", fail_if_loaded)
    with pytest.raises(ValueError, match="LAB_CONFIRMATION_REQUIRED"):
        asyncio.run(native_mcp.native_generate_speech(
            "Teste local.", "qwen3-serena"
        ))
