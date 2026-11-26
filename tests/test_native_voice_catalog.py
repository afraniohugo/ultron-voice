import hashlib,json,wave
import pytest
from ultron_voice.native_catalog import list_profiles,resolve_profile

def test_catalog_pending_and_rejects_arbitrary_paths(tmp_path):
    data=list_profiles(tmp_path,tmp_path)
    assert len(data["profiles"])==10
    assert data["verified"]==0 and not data["production_enabled"]
    with pytest.raises(ValueError,match="UNKNOWN_NATIVE_PROFILE"):
        resolve_profile("../bad",tmp_path)

def test_receipt_is_required_for_verified(tmp_path):
    batch=tmp_path/"qwen_voice_batch_v1";batch.mkdir()
    p=batch/"Ryan.wav"
    with wave.open(str(p),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b"\x00\x01"*240)
    assert list_profiles(tmp_path,tmp_path)["verified"]==0
    (batch/"receipt.json").write_text(json.dumps({"results":[{"speaker":"Ryan","sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"bytes":p.stat().st_size}]}))
    assert list_profiles(tmp_path,tmp_path)["verified"]==1

def test_whitelist_manifest(tmp_path):
    root=tmp_path/"profiles_lab";root.mkdir()
    p=root/"qwen3-serena.json";p.write_text("{}")
    assert resolve_profile("qwen3-serena",tmp_path)==("qwen3",p)
