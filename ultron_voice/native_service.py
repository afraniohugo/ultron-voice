"""Staged native voice API. Deliberately not registered on the active MCP."""
from __future__ import annotations
from pathlib import Path
import uuid
import wave
from . import native_catalog
from .gameguard import game_active
from .tts import TTSConfig, build_tts

def native_list() -> dict:
    return native_catalog.list_profiles()

def native_synthesize(text: str, profile_id: str, *, confirm_lab: bool=False) -> dict:
    if confirm_lab is not True:
        raise ValueError("LAB_CONFIRMATION_REQUIRED")
    if not isinstance(text,str) or not text.strip() or len(text)>280:
        raise ValueError("INVALID_TEXT")
    if game_active():
        raise RuntimeError("GAMEGUARD_ACTIVE")
    engine, manifest=native_catalog.resolve_profile(profile_id)
    dest=native_catalog.LAB_ROOT/"native_drafts"/(uuid.uuid4().hex+".wav")
    config=TTSConfig(engine=engine,model=str(manifest))
    build_tts(config).synthesize(text.strip(),dest,config)
    if not dest.is_file():
        raise RuntimeError("MISSING_WAV")
    try:
        with wave.open(str(dest),"rb") as w:
            if w.getnframes()<=0 or w.getsampwidth()!=2 or w.getcomptype()!="NONE":
                raise ValueError("invalid PCM")
    except (OSError,EOFError,ValueError,wave.Error) as exc:
        raise RuntimeError("INVALID_WAV") from exc
    return {"status":"DRAFT_REVIEW_REQUIRED","profile_id":profile_id,"engine":engine,
            "path":str(dest),"production_enabled":False}
