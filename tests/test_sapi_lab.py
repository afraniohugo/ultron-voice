"""SAPI CPU canary: no VoiceStudio, model downloads, GPU, or new service."""
from __future__ import annotations

import hashlib
import os
import sys
import wave
from pathlib import Path

import pytest

from ultron_voice import sapi as sapi_module
from ultron_voice.audiobook import AudiobookJob, audiobook
from ultron_voice.tts import TTSConfig, build_tts


def test_unknown_tts_engine_fails_closed():
    with pytest.raises(ValueError, match="Unknown local TTS"):
        build_tts(TTSConfig(engine="engine-not-known"))


def test_sapi_requires_explicit_local_voice(tmp_path, monkeypatch):
    monkeypatch.setattr(sapi_module, "game_active", lambda: False)
    tts = build_tts(TTSConfig(engine="sapi"))
    with pytest.raises(ValueError, match="SAPI_VOICE_REQUIRED"):
        tts.synthesize("Oi", tmp_path / "x.wav", TTSConfig(engine="sapi"))
    assert not (tmp_path / "x.wav").exists()


def test_sapi_gameguard_blocks_before_process(tmp_path, monkeypatch):
    monkeypatch.setattr(sapi_module, "game_active", lambda: True)
    def forbidden(*args, **kwargs):
        raise AssertionError("subprocess must never start during Warzone")
    monkeypatch.setattr(sapi_module.subprocess, "run", forbidden)
    config = TTSConfig(engine="sapi", model="Microsoft Maria Desktop")
    with pytest.raises(RuntimeError, match="GAMEGUARD_ACTIVE"):
        build_tts(config).synthesize("Teste", tmp_path / "blocked.wav", config)
    assert not (tmp_path / "blocked.wav").exists()


def test_sapi_real_local_ptbr_wav(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows-only SAPI")
    if sapi_module.game_active():
        pytest.skip("GameGuard active: no TTS during game")
    config = TTSConfig(engine="sapi", model="Microsoft Maria Desktop")
    path = tmp_path / "ptbr.wav"
    build_tts(config).synthesize("O Ultron Voice agora consegue falar sem o VoiceStudio.", path, config)
    with wave.open(str(path), "rb") as wav:
        assert wav.getnframes() > wav.getframerate() // 2
        assert wav.getcomptype() == "NONE"
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest()


def test_audiobook_real_ptbr_sapi_two_chapters(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows-only SAPI")
    if sapi_module.game_active():
        pytest.skip("GameGuard active: no TTS during game")
    out = tmp_path / "book_pt.wav"
    job = AudiobookJob("Lab PT-BR", [
        {"text": "Primeiro capítulo do Ultron Voice."},
        {"text": "Segundo capítulo, completamente local."},
    ], out, tts_engine="sapi", tts_model="Microsoft Maria Desktop")
    result = audiobook(job)
    assert result.exit_code == 0, result.error
    with wave.open(str(out), "rb") as wav:
        assert wav.getnframes() > wav.getframerate()
    assert result.checksums["output"] == hashlib.sha256(out.read_bytes()).hexdigest()

def test_sapi_missing_installed_ptbr_voice_fails_closed(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows-only")
    if sapi_module.game_active():
        pytest.skip("GameGuard active")
    config = TTSConfig(engine="sapi", model="Nonexistent Ultron Lab Voice")
    destination = tmp_path / "should_not_exist.wav"
    with pytest.raises(RuntimeError, match="SAPI_ENGINE_FAILED"):
        build_tts(config).synthesize("Teste.", destination, config)
    assert not destination.exists()


def test_sapi_to_vosk_real_local_chain(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows-only")
    if sapi_module.game_active():
        pytest.skip("GameGuard active")
    from backend.engine.asr.vosk_engine import _DEFAULT_models_DIR
    model = _DEFAULT_models_DIR / "vosk-model-small-pt-0.3"
    if not (model / "final.mdl").exists():
        pytest.skip("No local ASR model; never auto-download in tests")
    path = tmp_path / "speech_local.wav"
    config = TTSConfig(engine="sapi", model="Microsoft Maria Desktop")
    build_tts(config).synthesize(
        "A voz foi gerada sem acessar o VoiceStudio.", path, config
    )
    from backend.engine.asr import transcribe
    result = transcribe(str(path), language="pt", engine="vosk")
    assert not result.startswith("ERR:"), result
    assert len(result.strip().split()) >= 3
