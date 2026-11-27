"""ASR must refuse missing weights before importing or downloading engines."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from backend.engine.asr import create_engine
from backend.engine.asr.vosk_engine import VoskEngine
from ultron_voice import gameguard

@pytest.mark.parametrize("kind,code", [
    ("whisper","WHISPER_LOCAL_WEIGHTS_REQUIRED"),
    ("faster-whisper","FASTER_WHISPER_LOCAL_WEIGHTS_REQUIRED"),
])
def test_missing_local_weights(tmp_path, monkeypatch, kind, code):
    monkeypatch.setattr(gameguard,"game_active",lambda:False)
    monkeypatch.setitem(sys.modules,"whisper",None)
    monkeypatch.setitem(sys.modules,"faster_whisper",None)
    with pytest.raises(RuntimeError,match=code):
        create_engine(kind,models_dir=tmp_path).transcribe("fixture.wav")

def test_faster_whisper_local_only_cpu(tmp_path, monkeypatch):
    for name in ("config.json","model.bin","tokenizer.json"):
        (tmp_path/name).touch()
    monkeypatch.setattr(gameguard,"game_active",lambda:False)
    monkeypatch.setattr(VoskEngine,"_read_pcm",lambda self,path:(b"\0\0"*16000,16000))
    instance=Mock()
    instance.transcribe.return_value=([SimpleNamespace(text=" ola mundo ")],None)
    factory=Mock(return_value=instance)
    monkeypatch.setitem(sys.modules,"faster_whisper",SimpleNamespace(WhisperModel=factory))
    assert create_engine("faster-whisper",model=tmp_path).transcribe("fixture.wav")=="ola mundo"
    factory.assert_called_once_with(str(tmp_path.resolve()),device="cpu",compute_type="int8",
                                   cpu_threads=4,num_workers=1,local_files_only=True)
    assert instance.transcribe.call_args.kwargs["language"]=="pt"

def test_guard_precedes_import(tmp_path,monkeypatch):
    monkeypatch.setattr(gameguard,"game_active",lambda:True)
    for kind in ("whisper","faster-whisper"):
        with pytest.raises(RuntimeError,match="GAMEGUARD_ACTIVE"):
            create_engine(kind,models_dir=tmp_path).transcribe("fixture.wav")
