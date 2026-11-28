"""Ultron Voice: original, local interoperability adapter to the installed VoiceStudio CLI.

The installed VoiceStudio application remains separate; no upstream code is
copied or patched. Only fixed loopback endpoints and local files are used.
Generated audio remains DRAFT_REVIEW_REQUIRED; this is not a rights grant.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

VOICE_CLI = Path(r"E:\IA LOCAL\VoiceStudio\app\resources\cli\voicestudio.exe")
VOICE_URL = "http://127.0.0.1:3900"
STUDIO_URL = "http://127.0.0.1:8779"
STUDIO_AUDIO_ROOT = Path(r"E:\IA LOCAL\producoes\ultron_studio\audio_assets")
OUTPUT_ROOT = STUDIO_AUDIO_ROOT / "ultron_voice_drafts"
INPUT_ROOTS = (
    STUDIO_AUDIO_ROOT,
    Path(r"E:\IA LOCAL\media"),
    Path(r"E:\IA LOCAL\knowledge\hermes\recibos"),
)
GAME_NAMES = {"cod.exe", "warzone.exe", "modernwarfare.exe", "cod23.exe"}
IDENTITY_RE = re.compile(r"^[\w .\-]{1,100}$", re.UNICODE)
LANG_RE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")
MAX_TEXT = 1200


class VoiceError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code)


def _safe_error(exc: Exception) -> dict:
    if isinstance(exc, VoiceError):
        return {"ok": False, "error": exc.code, "detail": exc.detail[:180],
                "publication_allowed": False}
    return {"ok": False, "error": "LOCAL_BACKEND_ERROR",
            "detail": type(exc).__name__, "publication_allowed": False}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _get_json(url: str, timeout: float = 2.0) -> dict:
    if url not in (VOICE_URL + "/health", STUDIO_URL + "/api/status",
                   STUDIO_URL + "/api/audio/sources"):
        raise VoiceError("LOOPBACK_ONLY")
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(131073)
        if len(raw) > 131072:
            raise VoiceError("RESPONSE_TOO_LARGE")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {"response_type": type(obj).__name__}


def _check_game() -> bool:
    # Single fail-closed GameGuard sampler for the whole package: bounded
    # tasklist timeout and short cache, no per-bridge polling under load.
    from .gameguard import game_active
    return game_active()


def _require_safe() -> None:
    if _check_game():
        raise VoiceError("GAMEGUARD_ACTIVE", "Audio generation paused while gaming.")


def _require_backend() -> None:
    try:
        health = _get_json(VOICE_URL + "/health")
        if isinstance(health, dict) and health.get("ok") is False:
            raise VoiceError("VOICESTUDIO_NOT_HEALTHY")
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise VoiceError("VOICESTUDIO_BACKEND_OFFLINE",
                         "The installed VoiceStudio backend at 127.0.0.1:3900 must be started.") from exc


def _validate_identity(value: str, field: str) -> str:
    if not isinstance(value, str) or not IDENTITY_RE.fullmatch(value.strip()):
        raise VoiceError("INVALID_" + field.upper())
    return value.strip()


def _validate_text(value: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise VoiceError("INVALID_TEXT", f"Expected 1..{limit} characters.")
    if "\x00" in value:
        raise VoiceError("INVALID_TEXT")
    return value.strip()


def _language(value: str) -> str:
    if not isinstance(value, str) or not LANG_RE.fullmatch(value):
        raise VoiceError("INVALID_LANGUAGE")
    return value


def _output_file() -> Path:
    base = STUDIO_AUDIO_ROOT.resolve()
    output = OUTPUT_ROOT.resolve()
    if output != base and not output.is_relative_to(base):
        raise VoiceError("OUTPUT_ROOT_OUT_OF_SCOPE")
    output.mkdir(parents=True, exist_ok=True)
    return output / f"ultron_voice_{uuid.uuid4().hex}.wav"


def _allowed_input(raw: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise VoiceError("INPUT_PATH_REQUIRED")
    p = Path(raw)
    if not p.is_absolute() or not p.is_file() or p.is_symlink():
        raise VoiceError("INPUT_NOT_ALLOWED", "Input must exist in a permitted local audio directory.")
    actual = p.resolve(strict=True)
    if not any(actual.is_relative_to(root.resolve()) for root in INPUT_ROOTS):
        raise VoiceError("INPUT_NOT_ALLOWED", "Allowed: Studio audio staging, media, and canary receipts.")
    if actual.suffix.lower() not in {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus"}:
        raise VoiceError("UNSUPPORTED_AUDIO")
    if actual.stat().st_size > 128 * 1024 * 1024:
        raise VoiceError("INPUT_TOO_LARGE")
    return actual


def _call_cli(arguments: list[str], *, timeout: int = 160, requires_idle: bool = True) -> Any:
    if requires_idle:
        _require_safe()
    try:
        _require_backend()
    except VoiceError as exc:
        if (exc.code != "VOICESTUDIO_BACKEND_OFFLINE" or
                os.environ.get("ULTRON_VOICE_AUTOSTART_BACKEND") != "1"):
            raise
        boot = start_backend()
        if not boot.get("ok"):
            raise VoiceError("VOICESTUDIO_BOOT_FAILED",
                             str(boot.get("error", "unknown")))
        _require_backend()
    if not VOICE_CLI.is_file():
        raise VoiceError("VOICESTUDIO_CLI_MISSING")
    cmd = [str(VOICE_CLI), "--url", VOICE_URL, "--json", "--timeout",
           str(timeout), *arguments]
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    start = time.monotonic()
    while True:
        try:
            stdout, stderr = p.communicate(timeout=2)
            break
        except subprocess.TimeoutExpired:
            if (time.monotonic() - start) > timeout:
                p.kill()
                p.communicate()
                raise VoiceError("VOICE_TIMEOUT")
            if requires_idle and _check_game():
                p.kill()
                p.communicate()
                raise VoiceError("GAMEGUARD_INTERRUPTED")
    if p.returncode != 0:
        # CLI errors may contain prompts or paths: do not expose raw stderr.
        raise VoiceError("VOICESTUDIO_CLI_FAILED", "Native VoiceStudio command failed.")
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise VoiceError("VOICESTUDIO_INVALID_JSON") from exc


def health() -> dict:
    voice_online = False
    studio_online = False
    voice_details: dict = {}
    studio_details: dict = {}
    try:
        voice_details = _get_json(VOICE_URL + "/health")
        voice_online = True
    except Exception:
        pass
    try:
        studio_details = _get_json(STUDIO_URL + "/api/status")
        studio_online = True
    except Exception:
        pass
    return {
        "ok": True, "mcp_service": "ultron_voice", "stage": "INTEGRATION_CANARY",
        "voicestudio_installed": VOICE_CLI.is_file(),
        "voicestudio_backend_online": voice_online,
        "ultron_studio_online": studio_online,
        "studio_audio_staging": str(STUDIO_AUDIO_ROOT),
        "voice_endpoint": VOICE_URL, "studio_endpoint": STUDIO_URL,
        "gameguard_active": _check_game(),
        "publication_allowed": False,
        "notes": "VoiceStudio remains separate. Studio rights verification remains mandatory.",
    }


def voices() -> dict:
    try:
        response = _call_cli(["voices", "list"], timeout=12, requires_idle=False)
        return {"ok": True, "source": "voicestudio_local", "voices": response,
                "publication_allowed": False}
    except Exception as exc:
        return _safe_error(exc)


def engines() -> dict:
    try:
        response = _call_cli(["engines", "list"], timeout=12, requires_idle=False)
        return {"ok": True, "source": "voicestudio_local", "engines": response,
                "publication_allowed": False}
    except Exception as exc:
        return _safe_error(exc)


def synthesize(text: str, profile_id: str | None = None,
               engine: str | None = None, language: str = "pt",
               speed: float = 1.0) -> dict:
    path: Path | None = None
    try:
        clean = _validate_text(text)
        if not profile_id:
            raise VoiceError("VOICE_PROFILE_REQUIRED",
                             "Use list_voices to choose an installed voice. No automatic replacement.")
        profile = _validate_identity(profile_id, "profile")
        lang = _language(language)
        if not (0.5 <= float(speed) <= 1.6):
            raise VoiceError("INVALID_SPEED")
        _require_safe()
        path = _output_file()
        args = ["speak", "--voice", profile, "--language", lang,
                "--speed", str(speed), "--output", str(path)]
        if engine is not None:
            args.extend(["--engine", _validate_identity(engine, "engine")])
        # Text is a distinct argv element; never evaluated by a shell.
        args.append(clean)
        result = _call_cli(args, timeout=160)
        if not path.is_file() or path.stat().st_size < 44:
            raise VoiceError("AUDIO_NOT_CREATED")
        with path.open("rb") as fh:
            if fh.read(4) != b"RIFF":
                raise VoiceError("INVALID_WAV")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "ok": True, "engine": engine or "voicestudio_selected_profile",
            "voice_profile": profile, "language": lang,
            "path": str(path), "bytes": path.stat().st_size, "sha256": digest,
            "studio_catalog_scope": "STAGING_UNVERIFIED",
            "status": "DRAFT_REVIEW_REQUIRED", "publication_allowed": False,
            "rights_verified": False, "studio_audio_binding_allowed": False,
            "native_result_available": bool(result),
        }
    except Exception as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        return _safe_error(exc)


def speech_to_text(audio_path: str, language: str = "pt") -> dict:
    try:
        audio = _allowed_input(audio_path)
        _require_safe()
        transcript = _output_file().with_suffix(".txt")
        result = _call_cli(["transcribe", "--language", _language(language),
                            "--format", "text", "--output", str(transcript),
                            str(audio)], timeout=120)
        if not transcript.is_file():
            raise VoiceError("TRANSCRIPT_NOT_CREATED")
        content = transcript.read_text(encoding="utf-8").strip()
        return {"ok": True, "source": str(audio),
                "text": content, "transcript_path": str(transcript),
                "engine": "voicestudio_local", "publication_allowed": False,
                "status": "DRAFT_REVIEW_REQUIRED"}
    except Exception as exc:
        return _safe_error(exc)


def describe(description: str) -> dict:
    try:
        text = _validate_text(description, 400)
        result = _call_cli(["voices", "describe", text], timeout=30,
                           requires_idle=False)
        return {"ok": True, "description": result,
                "saved": False, "publication_allowed": False}
    except Exception as exc:
        return _safe_error(exc)


def design(description: str, profile_name: str, confirm_create: bool = False,
           language: str = "pt") -> dict:
    try:
        if not confirm_create:
            raise VoiceError("CONFIRM_CREATE_REQUIRED",
                             "Creates a saved voice in VoiceStudio; requires explicit confirmation.")
        text = _validate_text(description, 400)
        name = _validate_identity(profile_name, "profile_name")
        _require_safe()
        result = _call_cli(["voices", "design", "--name", name,
                            "--language", _language(language),
                            "--description", text], timeout=180)
        return {"ok": True, "result": result, "profile_name": name,
                "publication_allowed": False, "rights_verified": False}
    except Exception as exc:
        return _safe_error(exc)


def clone(ref_audio_path: str, profile_name: str, consent_confirmed: bool = False,
          language: str = "pt") -> dict:
    try:
        if not consent_confirmed:
            raise VoiceError("CONSENT_REQUIRED", "Voice owner consent must be verified.")
        source = _allowed_input(ref_audio_path)
        name = _validate_identity(profile_name, "profile_name")
        _require_safe()
        result = _call_cli(["voices", "clone", "--name", name,
                            "--language", _language(language),
                            "--audio", str(source)], timeout=180)
        return {"ok": True, "profile_name": name, "native_result": result,
                "publication_allowed": False, "rights_verified": False,
                "status": "CONSENT_AND_RIGHTS_REVIEW_REQUIRED"}
    except Exception as exc:
        return _safe_error(exc)


def studio_audio_handoff(audio_path: str) -> dict:
    """Confirm the draft is visible in the existing Studio source catalog.

    Does not grant licensing, link a timeline track, render, or publish.
    """
    try:
        p = _allowed_input(audio_path)
        if not p.resolve().is_relative_to(OUTPUT_ROOT.resolve()):
            raise VoiceError("NOT_ULTRON_VOICE_DRAFT")
        if not p.name.startswith("ultron_voice_") or p.suffix.lower() != ".wav":
            raise VoiceError("NOT_ULTRON_VOICE_DRAFT")
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        try:
            catalog = _get_json(STUDIO_URL + "/api/audio/sources")
        except Exception as exc:
            raise VoiceError("ULTRON_STUDIO_OFFLINE") from exc
        entry = next((item for item in catalog.get("items", [])
                      if isinstance(item, dict) and item.get("name") == p.name), None)
        if entry is None:
            return {"ok": False, "error": "STUDIO_SOURCE_NOT_DISCOVERED",
                    "sha256": digest, "publication_allowed": False}
        return {"ok": True, "studio_source_id": entry.get("id"),
                "studio_scope": entry.get("scope"), "sha256": digest,
                "rights_verified": False, "status": "STAGING_UNVERIFIED",
                "publication_allowed": False,
                "audio_binding_allowed": False}
    except Exception as exc:
        return _safe_error(exc)


def start_backend() -> dict:
    """Start the EXISTING VoiceStudio backend, once, headless; no new service or cron."""
    import socket
    try:
        try:
            _get_json(VOICE_URL + "/health")
            return {"ok": True, "status": "ALREADY_RUNNING",
                    "backend": VOICE_URL, "publication_allowed": False}
        except (OSError, ValueError, urllib.error.URLError):
            pass
        _require_safe()
        python = Path(r"E:\IA LOCAL\VoiceStudio\project\.venv\Scripts\python.exe")
        entry = Path(r"E:\IA LOCAL\VoiceStudio\project\backend\main.py")
        if not python.is_file() or not entry.is_file():
            raise VoiceError("VOICESTUDIO_INSTALL_INCOMPLETE")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.6)
            if s.connect_ex(("127.0.0.1", 3900)) == 0:
                raise VoiceError("BACKEND_PORT_OCCUPIED")
        receipt_dir = Path(r"E:\IA LOCAL\knowledge\hermes\recibos")
        receipt_dir.mkdir(parents=True, exist_ok=True)
        out = receipt_dir / "ultron_voice_native_backend.stdout.log"
        err = receipt_dir / "ultron_voice_native_backend.stderr.log"
        env = os.environ.copy()
        env.update({
            "OMNIVOICE_CACHE_DIR": r"E:\IA LOCAL\VoiceStudio\models",
            "HF_HOME": r"E:\IA LOCAL\VoiceStudio\models",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1", "OMNIVOICE_BIND_HOST": "127.0.0.1",
            "OMNIVOICE_PORT": "3900", "PYTHONUNBUFFERED": "1",
        })
        started = time.monotonic()
        with out.open("a", encoding="utf-8") as fout, err.open("a", encoding="utf-8") as ferr:
            process = subprocess.Popen(
                [str(python), str(entry)], cwd=str(entry.parent.parent),
                env=env, stdin=subprocess.DEVNULL, stdout=fout, stderr=ferr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        while time.monotonic() - started < 45:
            if _check_game():
                process.terminate()
                raise VoiceError("GAMEGUARD_INTERRUPTED")
            if process.poll() is not None:
                raise VoiceError("NATIVE_BACKEND_EXITED")
            try:
                _get_json(VOICE_URL + "/health")
                return {"ok": True, "status": "STARTED_HEADLESS",
                        "native_voice_backend_pid": process.pid,
                        "endpoint": VOICE_URL, "startup_seconds": round(time.monotonic()-started, 2),
                        "publication_allowed": False}
            except (OSError, ValueError, urllib.error.URLError):
                time.sleep(1)
        process.terminate()
        raise VoiceError("NATIVE_BACKEND_START_TIMEOUT")
    except Exception as exc:
        return _safe_error(exc)
