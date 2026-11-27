"""Offline model admission and incremental recognition contract."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from backend.engine.asr.vosk_engine import VoskEngine, VoskUnavailable
from ultron_voice import gameguard

def test_missing_model_does_not_extract_or_download(tmp_path):
    (tmp_path / "vosk-model-small-pt-0.3.zip").write_bytes(b"invalid archive")
    engine = VoskEngine(models_dir=tmp_path)
    with pytest.raises(VoskUnavailable, match="LOCAL_MODEL_REQUIRED"):
        engine._ensure_model("pt")
    assert len(list(tmp_path.iterdir())) == 1

def test_explicit_local_model_path(tmp_path):
    (tmp_path / "am").mkdir()
    (tmp_path / "am" / "final.mdl").touch()
    assert VoskEngine(model=tmp_path)._ensure_model("pt") == tmp_path.resolve()

def fixture_engine(tmp_path, monkeypatch):
    (tmp_path / "final.mdl").touch()
    model = Mock(return_value=object())
    recognizer = Mock()
    recognizer.AcceptWaveform.return_value = False
    recognizer.PartialResult.return_value = '{"partial":"ola"}'
    recognizer.FinalResult.return_value = '{"text":"ola mundo"}'
    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(
        Model=model, KaldiRecognizer=Mock(return_value=recognizer)))
    monkeypatch.setattr(gameguard, "game_active", lambda: False)
    return VoskEngine(model=tmp_path), model, recognizer

def test_partial_final_and_cached_model(tmp_path, monkeypatch):
    engine, model, recognizer = fixture_engine(tmp_path, monkeypatch)
    for _ in range(2):
        assert list(engine.transcribe_stream([b"\0\0"]*2)) == [
            {"type":"partial","text":"ola"}, {"type":"final","text":"ola mundo"}]
    assert model.call_count == 1

def test_invalid_pcm_and_rate_rejected(tmp_path, monkeypatch):
    engine, _, recognizer = fixture_engine(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="RATE_REQUIRED"):
        list(engine.transcribe_stream([b"\0\0"], sample_rate=8000))
    with pytest.raises(ValueError, match="INVALID_PCM"):
        list(engine.transcribe_stream([b"x"]))
    recognizer.AcceptWaveform.assert_not_called()

def test_gameguard_blocks_model_load(tmp_path, monkeypatch):
    engine, model, _ = fixture_engine(tmp_path, monkeypatch)
    monkeypatch.setattr(gameguard, "game_active", lambda: True)
    with pytest.raises(RuntimeError, match="GAMEGUARD_ACTIVE"):
        list(engine.transcribe_stream([b"\0\0"]))
    model.assert_not_called()
