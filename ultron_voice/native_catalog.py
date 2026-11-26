"""Lab-only native voice catalog; no VoiceStudio or network dependency."""
from __future__ import annotations
import json
import hashlib
import wave
from pathlib import Path

MODEL_ROOT = Path(r"E:\IA LOCAL\models\ultron_voice")
LAB_ROOT = Path(r"E:\IA LOCAL\lab\ultron-voice-recovery-20261125")
SPEAKERS = ("Aiden","Dylan","Eric","Ono_Anna","Ryan","Serena","Sohee","Uncle_Fu","Vivian")

def _receipt(path: Path) -> dict:
    try:
        data=json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):
        return {}

def _sample(path: Path, evidence: dict | None) -> dict:
    if not path.is_file() or path.is_symlink():
        return {"state":"PENDING","sample":None}
    try:
        with wave.open(str(path),"rb") as w:
            if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getnframes()<=0 or w.getcomptype()!="NONE":
                raise ValueError("bad WAV")
            duration=round(w.getnframes()/w.getframerate(),3)
            rate=w.getframerate()
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        verified=bool(evidence and evidence.get("sha256")==sha and evidence.get("bytes")==path.stat().st_size)
        return {"state":"WAV_VERIFIED" if verified else "WAV_PRESENT_RECEIPT_PENDING",
                "sample":str(path),"duration_s":duration,"rate":rate,"sha256":sha,
                "quality_review":"PENDING"}
    except (OSError,ValueError,EOFError,wave.Error):
        return {"state":"INVALID_WAV","sample":None}

def list_profiles(lab: Path=LAB_ROOT, models: Path=MODEL_ROOT) -> dict:
    batch=_receipt(lab/"qwen_voice_batch_v1"/"receipt.json")
    items={x.get("speaker"):x for x in batch.get("results",[]) if isinstance(x,dict)}
    profiles=[]
    for speaker in SPEAKERS:
        manifest=models/"profiles_lab"/("qwen3-"+speaker.lower()+".json")
        if speaker=="Serena":
            receipt=_receipt(lab/"canary_qwen_serena_receipt.json")
            sample=lab/"canary_qwen_serena_ptbr.wav"
        else:
            receipt=items.get(speaker,{})
            sample=lab/"qwen_voice_batch_v1"/(speaker+".wav")
        profiles.append(dict(id="qwen3-"+speaker.lower(),speaker=speaker,engine="qwen3",
                             language="Portuguese",manifest_present=manifest.is_file(),
                             **_sample(sample,receipt)))
    profiles.append(dict(id="chatterbox-ptbr",speaker="PT-BR",engine="chatterbox_ptbr",
                         language="pt-BR",manifest_present=(models/"chatterbox_f4_manifest.json").is_file(),
                         **_sample(lab/"canary_xpu_ptbr.wav",_receipt(lab/"canary_xpu_receipt.json"))))
    return {"scope":"laboratory_only","production_enabled":False,"profiles":profiles,
            "verified":sum(p["state"]=="WAV_VERIFIED" for p in profiles),
            "present":sum(p["sample"] is not None for p in profiles)}

def resolve_profile(profile_id: str, models: Path=MODEL_ROOT) -> tuple[str,Path]:
    allowed={"qwen3-"+name.lower():("qwen3",models/"profiles_lab"/("qwen3-"+name.lower()+".json")) for name in SPEAKERS}
    allowed["chatterbox-ptbr"]=("chatterbox_ptbr",models/"chatterbox_f4_manifest.json")
    if profile_id not in allowed:
        raise ValueError("UNKNOWN_NATIVE_PROFILE")
    engine,path=allowed[profile_id]
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(models.resolve()):
        raise ValueError("PROFILE_NOT_AVAILABLE")
    return engine,path
