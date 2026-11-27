import pytest
import wave
from ultron_voice import native_service as ns
def test_native_requires_lab_confirmation():
    with pytest.raises(ValueError,match="LAB_CONFIRMATION_REQUIRED"):
        ns.native_synthesize("teste","qwen3-serena")
def test_native_gameguard(monkeypatch):
    monkeypatch.setattr(ns,"game_active",lambda:True)
    with pytest.raises(RuntimeError,match="GAMEGUARD_ACTIVE"):
        ns.native_synthesize("teste","qwen3-serena",confirm_lab=True)
def test_native_draft_routes_only_whitelist(monkeypatch,tmp_path):
    monkeypatch.setattr(ns,"game_active",lambda:False)
    monkeypatch.setattr(ns.native_catalog,"LAB_ROOT",tmp_path)
    monkeypatch.setattr(ns.native_catalog,"resolve_profile",lambda profile:("qwen3",tmp_path/"profile.json"))
    class Fake:
        def synthesize(self,text,out,config):
            out.parent.mkdir(parents=True,exist_ok=True)
            with wave.open(str(out),"wb") as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b"\x00\x01"*240)
    monkeypatch.setattr(ns,"build_tts",lambda config:Fake())
    result=ns.native_synthesize("teste","qwen3-serena",confirm_lab=True)
    assert result["status"]=="DRAFT_REVIEW_REQUIRED"
    assert not result["production_enabled"]
