"""Qwen3-TTS CustomVoice: offline-only, direct local-weights adapter (F2).

No model download, VoiceStudio, network API, auto-start, publication, or GPU.
Weights and runtime must be installed deliberately in isolated directories.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from .gameguard import game_active

MODEL_ROOT = Path(r"E:\IA LOCAL\models\ultron_voice")
RUNTIME_ROOT = Path(r"E:\IA LOCAL\tools\ultron_voice_neural")
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
MODEL_LICENSE = "Apache-2.0"
SPEAKERS = frozenset({
    "Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan",
    "Aiden", "Ono_Anna", "Sohee",
})


class NeuralPreflightError(RuntimeError):
    pass


def _inside(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)
    except (OSError, ValueError):
        return False


def _path(raw: str, root: Path, *, expect_file: bool) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise NeuralPreflightError("NEURAL_PATH_REQUIRED")
    value = Path(raw)
    if not value.is_absolute() or value.is_symlink():
        raise NeuralPreflightError("NEURAL_PATH_NOT_ALLOWED")
    candidate = value.resolve()
    base = root.resolve()
    if not _inside(candidate, base):
        raise NeuralPreflightError("NEURAL_PATH_NOT_ALLOWED")
    if not (candidate.is_file() if expect_file else candidate.is_dir()):
        raise NeuralPreflightError("NEURAL_ARTIFACT_NOT_INSTALLED")
    return candidate


def inspect_manifest(raw_manifest: str) -> dict:
    """No imports of neural packages and no I/O beyond local files."""
    manifest = _path(raw_manifest, MODEL_ROOT, expect_file=True)
    if manifest.suffix.lower() != ".json" or manifest.stat().st_size > 8192:
        raise NeuralPreflightError("NEURAL_MANIFEST_INVALID")
    try:
        info = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NeuralPreflightError("NEURAL_MANIFEST_INVALID") from exc
    if not isinstance(info, dict):
        raise NeuralPreflightError("NEURAL_MANIFEST_INVALID")
    if info.get("source_model") != MODEL_ID or info.get("weights_license") != MODEL_LICENSE:
        raise NeuralPreflightError("NEURAL_MODEL_LICENSE_UNVERIFIED")
    if info.get("weights_license_reviewed") is not True:
        raise NeuralPreflightError("NEURAL_LICENSE_REVIEW_REQUIRED")
    if info.get("usage_scope") != "laboratory_only":
        raise NeuralPreflightError("NEURAL_LAB_SCOPE_REQUIRED")
    speaker = info.get("speaker")
    if not isinstance(speaker, str) or speaker not in SPEAKERS:
        raise NeuralPreflightError("NEURAL_SPEAKER_INVALID")
    if info.get("language") != "Portuguese":
        raise NeuralPreflightError("NEURAL_LANGUAGE_UNSUPPORTED")
    instruction = info.get("instruct", "")
    if not isinstance(instruction, str) or len(instruction) > 240:
        raise NeuralPreflightError("NEURAL_INSTRUCTION_INVALID")
    if instruction.strip():
        raise NeuralPreflightError("NEURAL_06B_INSTRUCTION_UNSUPPORTED")
    model_dir = _path(info.get("model_dir"), MODEL_ROOT, expect_file=False)
    runtime_python = _path(info.get("runtime_python"), RUNTIME_ROOT, expect_file=True)
    if runtime_python.name.lower() != "python.exe":
        raise NeuralPreflightError("NEURAL_RUNTIME_INVALID")
    missing = []
    for part in ("config.json", "generation_config.json",
                 "speech_tokenizer/config.json", "speech_tokenizer/model.safetensors"):
        asset = model_dir / part
        if not asset.is_file() or asset.is_symlink():
            missing.append(part)
    # Allow either a single safetensors checkpoint or a sharded index.
    if not any((model_dir / weight).is_file() and not (model_dir / weight).is_symlink()
               for weight in ("model.safetensors", "model.safetensors.index.json")):
        missing.append("model.safetensors")
    if missing:
        raise NeuralPreflightError("NEURAL_WEIGHTS_INCOMPLETE: " + ",".join(missing))
    return {
        "status": "READY_FOR_ISOLATED_LOCAL_CANARY",
        "source_model": MODEL_ID,
        "weights_license": MODEL_LICENSE,
        "scope": "laboratory_only",
        "model_dir": str(model_dir),
        "runtime_python": str(runtime_python),
        "speaker": speaker,
        "language": "Portuguese",
        "instruct": instruction,
    }


class Qwen3LocalTTS:
    def synthesize(self, text: str, out_path: Path, config) -> Path:
        if not isinstance(text, str) or not text.strip() or len(text) > 1400:
            raise ValueError("NEURAL_TEXT_INVALID")
        # Never load a neural model, even in the lab, while a game is running.
        if game_active():
            raise NeuralPreflightError("GAMEGUARD_ACTIVE")
        settings = inspect_manifest(config.model)
        output = Path(out_path)
        if output.suffix.lower() != ".wav":
            raise ValueError("NEURAL_WAV_ONLY")
        output.parent.mkdir(parents=True, exist_ok=True)
        worker = Path(__file__).with_name("neural_qwen_worker.py")
        if not worker.is_file():
            raise NeuralPreflightError("NEURAL_WORKER_MISSING")
        with tempfile.TemporaryDirectory(prefix="ultron_qwen_", dir=output.parent) as scratch:
            request_file = Path(scratch) / "request.json"
            draft_file = Path(scratch) / "voice.wav"
            request = dict(settings, text=text, output=str(draft_file))
            request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            # Do not expose unrelated app tokens/API keys to a neural runtime.
            allowed_env = {
                "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE",
                "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
                "COMMONPROGRAMFILES", "COMSPEC",
            }
            environment = {key: value for key, value in os.environ.items()
                           if key.upper() in allowed_env}
            environment.update({
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_TELEMETRY": "1",
                "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                "ULTRON_VOICE_NO_NETWORK": "1",
                "PYTHONNOUSERSITE": "1", "CUDA_VISIBLE_DEVICES": "",
                "OMP_NUM_THREADS": "2",
            })
            # No shell. Only a curated, explicitly provided local Python runtime.
            process = subprocess.Popen(
                [settings["runtime_python"], "-I", str(worker), str(request_file)],
                cwd=str(Path(scratch)),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            start = time.monotonic()
            try:
                while True:
                    try:
                        process.communicate(timeout=3)
                        break
                    except subprocess.TimeoutExpired:
                        if game_active():
                            process.kill()
                            process.communicate()
                            raise NeuralPreflightError("GAMEGUARD_ACTIVE")
                        if time.monotonic() - start > 300:
                            process.kill()
                            process.communicate()
                            raise NeuralPreflightError("NEURAL_WORKER_TIMEOUT")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            if process.returncode != 0:
                # Never echo arbitrary stderr: model/runtime paths can be sensitive.
                raise NeuralPreflightError("NEURAL_WORKER_FAILED")
            if not draft_file.is_file() or draft_file.stat().st_size < 80:
                raise NeuralPreflightError("NEURAL_NO_AUDIO")
            with wave.open(str(draft_file), "rb") as wav:
                if wav.getcomptype() != "NONE" or wav.getnframes() == 0:
                    raise NeuralPreflightError("NEURAL_INVALID_WAV")
            if game_active():
                raise NeuralPreflightError("GAMEGUARD_ACTIVE")
            os.replace(draft_file, output)
        return output
