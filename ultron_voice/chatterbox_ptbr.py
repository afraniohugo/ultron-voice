"""Chatterbox PT-BR F4: audited local weights and isolated CPU worker.

No user-voice cloning, external services, HF cache access, new endpoints,
GPU or publication. Synthetic Qwen lab reference only, explicitly hashed.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from .gameguard import game_active

MODEL_ID = "ResembleAI/Chatterbox-Multilingual-pt-br"
MODEL_REV = "b3952f18bc2eaa72b9bd7c17d2c4653bcad4770d"
BASE_REV = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
SPACE_REV = "9e515821e826e207cd617a0fdd0223899ed108ea"
SOURCE_ROOT = Path(r"E:\IA LOCAL\tools\ultron_voice_chatterbox")
MODELS_ROOT = Path(r"E:\IA LOCAL\models\ultron_voice")
LOG_ROOT = Path(r"E:\IA LOCAL\logs\ultron_voice")
REFERENCE_HASH = "9f1e59f418eb12b5c8d2bea5928f8e716823387f6d65cbd47ee5d88baa6fe947"
FILES = (
    "t3_pt_br.safetensors", "s3gen_v3.pt",
    "grapheme_mtl_merged_expanded_v1.json", "ve.pt", "conds.pt",
)
PINNED_SHAS = {
    "t3_pt_br.safetensors": "074aaf65255eb9cb960288f7cc72e09d3b5008f6e0b14868c0d4e5b0bd7cbb6c",
    "s3gen_v3.pt": "f7abce4b196dae2d08d9296cbebc6521b046079577643b42a19a03499d08721e",
    "grapheme_mtl_merged_expanded_v1.json": "69632f47220a788a52ce2661d096453c5655e9bf25289d89a8d832c46ee07dbf",
    "ve.pt": "4b16d836bc598509860f6fa068165a8bb5e9ac84f05582dfcf278a5a372879f1",
    "conds.pt": "6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e",
}
SOURCE_TREE_SHA256 = "2d069415e18693bbe3cb850fd105b91d60cab923d44d7838622e3f2ef9c8adfa"


class ChatterboxPreflightError(RuntimeError):
    """Controlled failure, no path secrets / exception chaining in logs."""


def _local(raw: str, base: Path, *, is_file: bool) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ChatterboxPreflightError("CHATTERBOX_PATH_REQUIRED")
    path = Path(raw)
    if not path.is_absolute() or path.is_symlink():
        raise ChatterboxPreflightError("CHATTERBOX_PATH_REJECTED")
    resolved = path.resolve()
    root = base.resolve()
    if not (resolved == root or resolved.is_relative_to(root)):
        raise ChatterboxPreflightError("CHATTERBOX_PATH_REJECTED")
    if not (resolved.is_file() if is_file else resolved.is_dir()):
        raise ChatterboxPreflightError("CHATTERBOX_ARTIFACT_MISSING")
    return resolved


def _sha256(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as handle:
        while block := handle.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def inspect_manifest(manifest_path: str) -> dict:
    """Fail-closed before importing Torch; signed provenance by pinned hashes."""
    manifest = _local(manifest_path, MODELS_ROOT, is_file=True)
    if manifest.suffix.lower() != ".json" or manifest.stat().st_size > 8192:
        raise ChatterboxPreflightError("CHATTERBOX_MANIFEST_INVALID")
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ChatterboxPreflightError("CHATTERBOX_MANIFEST_INVALID") from exc
    if not isinstance(doc, dict):
        raise ChatterboxPreflightError("CHATTERBOX_MANIFEST_INVALID")
    if (doc.get("source_model") != MODEL_ID or doc.get("revision") != MODEL_REV or
            doc.get("weights_license") != "MIT" or
            doc.get("license_reviewed") is not True):
        raise ChatterboxPreflightError("CHATTERBOX_LICENSE_REVISION_FAILED")
    if doc.get("usage_scope") != "laboratory_only":
        raise ChatterboxPreflightError("CHATTERBOX_LAB_ONLY")
    if doc.get("language") != "pt":
        raise ChatterboxPreflightError("CHATTERBOX_LANGUAGE_INVALID")
    if doc.get("reference_source") != "synthetic_qwen_lab":
        raise ChatterboxPreflightError("CHATTERBOX_REFERENCE_CONSENT_GATE")
    def numeric(name: str, low: float, high: float):
        value = doc.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ChatterboxPreflightError("CHATTERBOX_PARAMETER_INVALID")
        if not low <= value <= high:
            raise ChatterboxPreflightError("CHATTERBOX_PARAMETER_INVALID")
        return float(value)
    exaggeration = numeric("exaggeration", .25, 1.0)
    cfg_weight = numeric("cfg_weight", .2, .8)
    temperature = numeric("temperature", .2, 1.5)
    model_dir = _local(doc.get("model_dir"), MODELS_ROOT, is_file=False)
    source_dir = _local(doc.get("source_dir"), SOURCE_ROOT, is_file=False)
    runtime = _local(doc.get("runtime_python"), SOURCE_ROOT, is_file=True)
    receipt = _local(doc.get("weights_receipt"), LOG_ROOT, is_file=True)
    reference = _local(doc.get("reference_audio"), LOG_ROOT, is_file=True)
    if runtime.name.lower() != "python.exe":
        raise ChatterboxPreflightError("CHATTERBOX_RUNTIME_INVALID")
    if source_dir != (SOURCE_ROOT / "space_src" / "chatterbox" / "src").resolve():
        raise ChatterboxPreflightError("CHATTERBOX_SOURCE_UNTRUSTED")
    if model_dir != (MODELS_ROOT / "chatterbox_ptbr").resolve():
        raise ChatterboxPreflightError("CHATTERBOX_MODEL_ROOT_INVALID")
    if reference != (LOG_ROOT / "neural_f3_20261122" / "qwen3_ptbr_lab.wav").resolve():
        raise ChatterboxPreflightError("CHATTERBOX_REFERENCE_UNAPPROVED")
    if _sha256(reference) != REFERENCE_HASH:
        raise ChatterboxPreflightError("CHATTERBOX_REFERENCE_CHANGED")
    try:
        audit = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ChatterboxPreflightError("CHATTERBOX_AUDIT_INVALID") from exc
    if (audit.get("status") != "FILES_VERIFIED_INFERENCE_NOT_VALIDATED" or
            audit.get("license") != "MIT (model card verified for both weights repositories)" or
            audit.get("source_space", {}).get("rev") != SPACE_REV):
        raise ChatterboxPreflightError("CHATTERBOX_AUDIT_INVALID")
    entries = audit.get("files", [])
    if not isinstance(entries, list):
        raise ChatterboxPreflightError("CHATTERBOX_AUDIT_INVALID")
    by_name = {it.get("file"): it for it in entries if isinstance(it, dict)}
    if set(by_name) != set(FILES):
        raise ChatterboxPreflightError("CHATTERBOX_AUDIT_MISSING_WEIGHTS")
    for name in FILES:
        artifact = model_dir / name
        entry = by_name[name]
        required_rev = MODEL_REV if name in FILES[:3] else BASE_REV
        if entry.get("revision") != required_rev or artifact.is_symlink() or not artifact.is_file():
            raise ChatterboxPreflightError("CHATTERBOX_WEIGHTS_INVALID")
        digest = _sha256(artifact)
        if (artifact.stat().st_size != entry.get("size") or
                digest != entry.get("sha256") or digest != PINNED_SHAS[name]):
            raise ChatterboxPreflightError("CHATTERBOX_WEIGHTS_HASH_MISMATCH")
    source_tree = source_dir / "chatterbox"
    if not (source_tree / "tts.py").is_file():
        raise ChatterboxPreflightError("CHATTERBOX_SOURCE_MISSING")
    code_files = sorted(source_tree.rglob("*.py"))
    source_hash = hashlib.sha256()
    for file in code_files:
        if file.is_symlink() or not file.is_file():
            raise ChatterboxPreflightError("CHATTERBOX_SOURCE_UNTRUSTED")
        source_hash.update(file.relative_to(source_tree).as_posix().encode("utf-8"))
        source_hash.update(file.read_bytes())
    if source_hash.hexdigest() != SOURCE_TREE_SHA256:
        raise ChatterboxPreflightError("CHATTERBOX_SOURCE_HASH_MISMATCH")
    return {
        "status": "READY_FOR_ISOLATED_CHATTR_PTBR",
        "model_dir": str(model_dir), "source_dir": str(source_dir),
        "runtime_python": str(runtime), "reference_audio": str(reference),
        "reference_sha256": REFERENCE_HASH, "language": "pt",
        "exaggeration": exaggeration, "cfg_weight": cfg_weight,
        "temperature": temperature, "scope": "laboratory_only",
    }


class ChatterboxPtBrTTS:
    def synthesize(self, text: str, out_path: Path, config) -> Path:
        if not isinstance(text, str) or not text.strip() or len(text) > 280:
            raise ValueError("CHATTERBOX_TEXT_INVALID")
        if game_active():
            raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
        settings = inspect_manifest(config.model)
        output = Path(out_path)
        if output.suffix.lower() != ".wav":
            raise ValueError("CHATTERBOX_WAV_ONLY")
        output.parent.mkdir(parents=True, exist_ok=True)
        worker = Path(__file__).with_name("chatterbox_worker.py")
        if not worker.is_file():
            raise ChatterboxPreflightError("CHATTERBOX_WORKER_MISSING")
        with tempfile.TemporaryDirectory(prefix="uv_chatterbox_", dir=output.parent) as tmp:
            request_path = Path(tmp) / "request.json"
            draft = Path(tmp) / "voice.wav"
            request_path.write_text(
                json.dumps(dict(settings, text=text, output=str(draft)), ensure_ascii=False),
                encoding="utf-8",
            )
            allow = {
                "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE",
                "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "COMSPEC",
            }
            env = {key: value for key, value in os.environ.items() if key.upper() in allow}
            env.update({
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "CUDA_VISIBLE_DEVICES": "",
                "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4",
                "PYTHONNOUSERSITE": "1",
            })
            process = subprocess.Popen(
                [settings["runtime_python"], "-I", str(worker), str(request_path)],
                cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            started = time.monotonic()
            try:
                while True:
                    try:
                        process.communicate(timeout=3)
                        break
                    except subprocess.TimeoutExpired:
                        if game_active():
                            process.kill()
                            process.communicate()
                            raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
                        if time.monotonic() - started > 480:
                            process.kill()
                            process.communicate()
                            raise ChatterboxPreflightError("CHATTERBOX_TIMEOUT")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            if process.returncode != 0:
                raise ChatterboxPreflightError("CHATTERBOX_WORKER_FAILED")
            if not draft.is_file() or draft.stat().st_size < 80:
                raise ChatterboxPreflightError("CHATTERBOX_AUDIO_MISSING")
            with wave.open(str(draft), "rb") as wav:
                if wav.getnframes() == 0 or wav.getcomptype() != "NONE":
                    raise ChatterboxPreflightError("CHATTERBOX_AUDIO_INVALID")
            if game_active():
                raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
            os.replace(draft, output)
        return output
