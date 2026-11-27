"""Focused integration contracts: Ultron Voice remains an independent MCP client of VoiceStudio."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock
import pytest

from ultron_voice import voicestudio_bridge as bridge


def test_health_reports_disabled_publication(monkeypatch):
    monkeypatch.setattr(bridge, "_get_json", lambda u: {"ok": True})
    monkeypatch.setattr(bridge, "_check_game", lambda: False)
    monkeypatch.setattr(bridge.VOICE_CLI.__class__, "is_file", lambda self: True)
    result = bridge.health()
    assert result["ok"] is True
    assert result["ultron_studio_online"] is True
    assert result["voicestudio_backend_online"] is True
    assert result["publication_allowed"] is False


def test_requires_chosen_profile(monkeypatch):
    result = bridge.synthesize("Teste de voz sem identidade.")
    assert result["ok"] is False
    assert result["error"] == "VOICE_PROFILE_REQUIRED"


def test_rejects_warzone_before_render(monkeypatch):
    monkeypatch.setattr(bridge, "_check_game", lambda: True)
    result = bridge.synthesize("Apenas teste.", profile_id="demo0001")
    assert result["error"] == "GAMEGUARD_ACTIVE"


def test_rejects_bad_names_and_language():
    assert bridge.synthesize("hi", profile_id="../unsafe")["error"] == "INVALID_PROFILE"
    assert bridge.synthesize("hi", profile_id="demo0001", language="en;curl")["error"] == "INVALID_LANGUAGE"


def test_generation_is_staging_only(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "STUDIO_AUDIO_ROOT", tmp_path)
    monkeypatch.setattr(bridge, "OUTPUT_ROOT", tmp_path / "ultron_voice_drafts")
    monkeypatch.setattr(bridge, "_check_game", lambda: False)
    def fake_cli(args, **kwargs):
        assert args[0] == "speak"
        assert args[args.index("--voice") + 1] == "demo0001"
        p = Path(args[args.index("--output") + 1])
        p.write_bytes(b"RIFF" + bytes(96))
        return {"output": str(p)}
    monkeypatch.setattr(bridge, "_call_cli", fake_cli)
    result = bridge.synthesize("Uma frase curta para teste.", profile_id="demo0001")
    assert result["ok"] is True
    assert result["rights_verified"] is False
    assert result["publication_allowed"] is False
    assert result["status"] == "DRAFT_REVIEW_REQUIRED"
    assert Path(result["path"]).parent == tmp_path / "ultron_voice_drafts"
    assert result["sha256"] == hashlib.sha256(Path(result["path"]).read_bytes()).hexdigest()


def test_unsafe_source_rejected():
    assert bridge.speech_to_text("C:\\Windows\\system.ini")["error"] == "INPUT_NOT_ALLOWED"


def test_clone_requires_consent_without_execution(monkeypatch):
    monkeypatch.setattr(bridge, "_call_cli", lambda *a, **k: pytest.fail("must not reach CLI"))
    assert bridge.clone("any.wav", "lab-voice")["error"] == "CONSENT_REQUIRED"


def test_design_requires_explicit_creation(monkeypatch):
    monkeypatch.setattr(bridge, "_call_cli", lambda *a, **k: pytest.fail("must not reach CLI"))
    assert bridge.design("calm", "lab-profile")["error"] == "CONFIRM_CREATE_REQUIRED"


def test_failed_synthesis_cannot_leave_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "STUDIO_AUDIO_ROOT", tmp_path)
    monkeypatch.setattr(bridge, "OUTPUT_ROOT", tmp_path / "ultron_voice_drafts")
    monkeypatch.setattr(bridge, "_check_game", lambda: False)
    def fail_after_write(args, **kwargs):
        Path(args[args.index("--output") + 1]).write_bytes(b"RIFF" + bytes(90))
        raise bridge.VoiceError("CLI_FAILED")
    monkeypatch.setattr(bridge, "_call_cli", fail_after_write)
    r = bridge.synthesize("Teste", "demo0001")
    assert r["error"] == "CLI_FAILED"
    assert not list((tmp_path / "ultron_voice_drafts").glob("*.wav"))


def test_handoff_studio_does_not_grant_rights(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "STUDIO_AUDIO_ROOT", tmp_path)
    monkeypatch.setattr(bridge, "OUTPUT_ROOT", tmp_path / "ultron_voice_drafts")
    monkeypatch.setattr(bridge, "INPUT_ROOTS", (tmp_path,))
    f = tmp_path / "ultron_voice_drafts" / "ultron_voice_test.wav"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"RIFF" + bytes(70))
    monkeypatch.setattr(bridge, "_get_json", lambda url: {"items": [
        {"id": "source_safe", "name": f.name, "scope": "STAGING_UNVERIFIED"}]})
    r = bridge.studio_audio_handoff(str(f))
    assert r["ok"] and r["studio_source_id"] == "source_safe"
    assert r["publication_allowed"] is False
    assert r["audio_binding_allowed"] is False


def test_voice_module_mcp_exposes_expected_tools():
    from ultron_voice.mcp import server
    import asyncio
    names = {t.name for t in asyncio.run(server.list_tools())}
    assert {"generate_speech","check_health","list_voices",
            "transcribe","studio_audio_handoff"}.issubset(names)
