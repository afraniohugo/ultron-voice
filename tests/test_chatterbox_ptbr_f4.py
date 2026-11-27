"""F4 audited offline Brazilian Portuguese Chatterbox adapter contract tests.

No real model imports, downloads, voice cloning or GPU. Real canary is separate.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import pytest

from ultron_voice import chatterbox_ptbr as cb
from ultron_voice.cli import main as cli_main
from ultron_voice.tts import TTSConfig, build_tts


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setup_lab(tmp_path, monkeypatch):
    root_models = tmp_path / "models"
    root_tools = tmp_path / "tools"
    root_logs = tmp_path / "logs"
    md = root_models / "chatterbox_ptbr"
    src = root_tools / "space_src" / "chatterbox" / "src"
    venv = root_tools / ".venv" / "Scripts"
    audit_dir = root_logs / "chatterbox_f4_20261122"
    reference = root_logs / "neural_f3_20261122" / "qwen3_ptbr_lab.wav"
    for path in (md, src / "chatterbox", venv, audit_dir, reference.parent):
        path.mkdir(parents=True, exist_ok=True)
    (src / "chatterbox" / "tts.py").write_text("# lab fixture", encoding="utf-8")
    (venv / "python.exe").write_bytes(b"fake executable")
    with wave.open(str(reference), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\0\1" * 24000)
    entries = []
    for index, name in enumerate(cb.FILES):
        p = md / name
        p.write_bytes(bytes([index + 1]) * 70)
        entries.append({
            "file": name, "size": 70, "sha256": _hash(p),
            "revision": cb.MODEL_REV if index < 3 else cb.BASE_REV,
        })
    receipt = audit_dir / "weights_receipt.json"
    receipt.write_text(json.dumps({
        "status": "FILES_VERIFIED_INFERENCE_NOT_VALIDATED",
        "license": "MIT (model card verified for both weights repositories)",
        "source_space": {"rev": cb.SPACE_REV},
        "files": entries,
    }), encoding="utf-8")
    payload = {
        "source_model": cb.MODEL_ID,
        "revision": cb.MODEL_REV,
        "weights_license": "MIT", "license_reviewed": True,
        "usage_scope": "laboratory_only",
        "language": "pt",
        "reference_source": "synthetic_qwen_lab",
        "model_dir": str(md), "source_dir": str(src),
        "runtime_python": str(venv / "python.exe"),
        "weights_receipt": str(receipt),
        "reference_audio": str(reference),
        "exaggeration": .55, "cfg_weight": .4, "temperature": .8,
    }
    manifest = root_models / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(cb, "MODELS_ROOT", root_models)
    monkeypatch.setattr(cb, "SOURCE_ROOT", root_tools)
    monkeypatch.setattr(cb, "LOG_ROOT", root_logs)
    monkeypatch.setattr(cb, "REFERENCE_HASH", _hash(reference))
    monkeypatch.setattr(cb, "PINNED_SHAS", {name: _hash(md / name) for name in cb.FILES})
    source_hash = hashlib.sha256()
    source_file = src / "chatterbox" / "tts.py"
    source_hash.update(b"tts.py")
    source_hash.update(source_file.read_bytes())
    monkeypatch.setattr(cb, "SOURCE_TREE_SHA256", source_hash.hexdigest())
    return manifest, payload, md, reference, receipt


def test_chatterbox_engine_is_registered():
    t = build_tts(TTSConfig(engine="chatterbox_ptbr", model="unused"))
    assert isinstance(t, cb.ChatterboxPtBrTTS)


def test_manifest_fixtures_pass(tmp_path, monkeypatch):
    manifest, *_ = setup_lab(tmp_path, monkeypatch)
    obj = cb.inspect_manifest(str(manifest))
    assert obj["status"] == "READY_FOR_ISOLATED_CHATTR_PTBR"
    assert obj["language"] == "pt" and obj["scope"] == "laboratory_only"


@pytest.mark.parametrize("field,bad,error", [
    ("source_model", "OTHER", "CHATTERBOX_LICENSE_REVISION_FAILED"),
    ("revision", "latest", "CHATTERBOX_LICENSE_REVISION_FAILED"),
    ("weights_license", "CC-BY-NC", "CHATTERBOX_LICENSE_REVISION_FAILED"),
    ("license_reviewed", False, "CHATTERBOX_LICENSE_REVISION_FAILED"),
    ("usage_scope", "post_commercial", "CHATTERBOX_LAB_ONLY"),
    ("language", "pt-BR", "CHATTERBOX_LANGUAGE_INVALID"),
    ("reference_source", "owner_voice", "CHATTERBOX_REFERENCE_CONSENT_GATE"),
    ("temperature", 1.9, "CHATTERBOX_PARAMETER_INVALID"),
    ("cfg_weight", 0.1, "CHATTERBOX_PARAMETER_INVALID"),
    ("exaggeration", True, "CHATTERBOX_PARAMETER_INVALID"),
])
def test_manifest_gates(tmp_path, monkeypatch, field, bad, error):
    manifest, payload, *_ = setup_lab(tmp_path, monkeypatch)
    payload[field] = bad
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(cb.ChatterboxPreflightError, match=error):
        cb.inspect_manifest(str(manifest))


def test_missing_weights_fails_closed(tmp_path, monkeypatch):
    manifest, _, md, *_ = setup_lab(tmp_path, monkeypatch)
    (md / "ve.pt").unlink()
    with pytest.raises(cb.ChatterboxPreflightError, match="CHATTERBOX_WEIGHTS_INVALID"):
        cb.inspect_manifest(str(manifest))


def test_mutated_weight_hash_fails_closed(tmp_path, monkeypatch):
    manifest, _, md, *_ = setup_lab(tmp_path, monkeypatch)
    (md / "t3_pt_br.safetensors").write_bytes(b"Q" * 70)
    with pytest.raises(cb.ChatterboxPreflightError, match="CHATTERBOX_WEIGHTS_HASH_MISMATCH"):
        cb.inspect_manifest(str(manifest))


def test_mutated_reference_fails_closed(tmp_path, monkeypatch):
    manifest, _, _, reference, _ = setup_lab(tmp_path, monkeypatch)
    reference.write_bytes(reference.read_bytes() + b"x")
    with pytest.raises(cb.ChatterboxPreflightError, match="CHATTERBOX_REFERENCE_CHANGED"):
        cb.inspect_manifest(str(manifest))


def test_mutated_source_code_is_blocked(tmp_path, monkeypatch):
    manifest, payload, *_ = setup_lab(tmp_path, monkeypatch)
    source = Path(payload["source_dir"]) / "chatterbox" / "tts.py"
    source.write_bytes(b"# injected change")
    with pytest.raises(cb.ChatterboxPreflightError, match="CHATTERBOX_SOURCE_HASH_MISMATCH"):
        cb.inspect_manifest(str(manifest))


def test_external_model_path_is_rejected(tmp_path, monkeypatch):
    manifest, payload, *_ = setup_lab(tmp_path, monkeypatch)
    payload["model_dir"] = str(tmp_path / "outside")
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(cb.ChatterboxPreflightError, match="CHATTERBOX_PATH_REJECTED"):
        cb.inspect_manifest(str(manifest))


def test_gameguard_blocks_before_checking_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "game_active", lambda: True)
    config = TTSConfig(engine="chatterbox_ptbr", model=str(tmp_path / "missing.json"))
    with pytest.raises(cb.ChatterboxPreflightError, match="GAMEGUARD_ACTIVE"):
        build_tts(config).synthesize("Olá.", tmp_path / "out.wav", config)
    assert not (tmp_path / "out.wav").exists()


def _fake_wave(dest):
    with wave.open(str(dest), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(24000)
        file.writeframes(b"\0\1" * 24000)


def test_fake_worker_offline_atomic_and_token_filtered(tmp_path, monkeypatch):
    manifest, *_ = setup_lab(tmp_path, monkeypatch)
    monkeypatch.setattr(cb, "game_active", lambda: False)
    monkeypatch.setenv("HF_TOKEN", "secret-not-forwarded")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-not-forwarded")
    records = []
    devices = []
    class Worker:
        returncode = 0
        def __init__(self, args, **opts):
            records.append((args, opts))
            assert args[1] == "-I"
            data = json.loads(Path(args[3]).read_text(encoding="utf-8"))
            devices.append(data["device"])
            assert data["language"] == "pt"
            self.returncode = 5 if data["device"] == "xpu" else 0
            if self.returncode == 0:
                _fake_wave(data["output"])
        def communicate(self, timeout=None): return b"", b""
        def poll(self): return self.returncode
    monkeypatch.setattr(cb.subprocess, "Popen", Worker)
    config = TTSConfig(engine="chatterbox_ptbr", model=str(manifest))
    destination = tmp_path / "out.wav"
    destination.write_bytes(b"old")
    assert build_tts(config).synthesize("Olá, Brasil.", destination, config) == destination
    with wave.open(str(destination), "rb") as audio:
        assert audio.getframerate() == 24000 and audio.getnframes() == 24000
    assert devices == ["xpu", "cpu"]
    env = records[-1][1]["env"]
    assert env["HF_HUB_OFFLINE"] == "1"
    assert env["CUDA_VISIBLE_DEVICES"] == ""
    assert "HF_TOKEN" not in env and "OPENAI_API_KEY" not in env


def test_failure_preserves_original_wav(tmp_path, monkeypatch):
    manifest, *_ = setup_lab(tmp_path, monkeypatch)
    monkeypatch.setattr(cb, "game_active", lambda: False)
    class Worker:
        returncode = 5
        def __init__(self, *a, **kw): pass
        def communicate(self, timeout=None): return b"", b""
        def poll(self): return 5
    monkeypatch.setattr(cb.subprocess, "Popen", Worker)
    config = TTSConfig(engine="chatterbox_ptbr", model=str(manifest))
    path = tmp_path / "keep.wav"
    path.write_bytes(b"keep me")
    with pytest.raises(cb.ChatterboxPreflightError, match="CHATTERBOX_WORKER_FAILED"):
        build_tts(config).synthesize("Teste.", path, config)
    assert path.read_bytes() == b"keep me"


def test_gameguard_during_worker_kills(tmp_path, monkeypatch):
    manifest, *_ = setup_lab(tmp_path, monkeypatch)
    states = iter([False, False, True])
    monkeypatch.setattr(cb, "game_active", lambda: next(states))
    killed = []
    class Worker:
        returncode = None
        def __init__(self, *a, **kw): pass
        def communicate(self, timeout=None):
            if not killed: raise subprocess.TimeoutExpired("python", 3)
            return b"", b""
        def poll(self): return None if not killed else 1
        def kill(self): killed.append(True); self.returncode = 1
    monkeypatch.setattr(cb.subprocess, "Popen", Worker)
    config = TTSConfig(engine="chatterbox_ptbr", model=str(manifest))
    with pytest.raises(cb.ChatterboxPreflightError, match="GAMEGUARD_ACTIVE"):
        build_tts(config).synthesize("Teste.", tmp_path / "out.wav", config)
    assert killed


def test_cli_bad_manifest_does_not_claim_success(tmp_path, capsys):
    rc = cli_main(["audiobook", "--title", "pt-br lab",
        "--chapters", '[{"text":"Olá."}]', "--tts-engine", "chatterbox_ptbr",
        "--tts-model", str(tmp_path / "no.json"),
        "--registry", str(tmp_path / "history.db"),
        "--log-dir", str(tmp_path / "log"),
        str(tmp_path / "no.wav")])
    assert rc == 1
    printed = capsys.readouterr()
    assert "OK:" not in printed.out
    assert "ERRO:" in printed.err
    assert not (tmp_path / "no.wav").exists()
