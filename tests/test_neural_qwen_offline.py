"""Offline neural F2 contracts. No downloaded weights, no GPU, no network."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import pytest

from ultron_voice import neural_qwen as qwen
from ultron_voice.tts import TTSConfig, build_tts
from ultron_voice.cli import main as cli_main


def _setup(tmp_path, monkeypatch):
    models = tmp_path / "models"
    runtime = tmp_path / "tools"
    model = models / "custom_voice"
    model.joinpath("speech_tokenizer").mkdir(parents=True)
    runtime.mkdir()
    (runtime / "python.exe").write_bytes(b"fake executable for contract test")
    for part in ("config.json", "generation_config.json",
                 "speech_tokenizer/config.json",
                 "speech_tokenizer/model.safetensors", "model.safetensors"):
        (model / part).write_bytes(b"fixture")
    monkeypatch.setattr(qwen, "MODEL_ROOT", models)
    monkeypatch.setattr(qwen, "RUNTIME_ROOT", runtime)
    manifest = models / "neural.json"
    payload = {
        "source_model": qwen.MODEL_ID,
        "weights_license": qwen.MODEL_LICENSE,
        "weights_license_reviewed": True,
        "usage_scope": "laboratory_only",
        "model_dir": str(model),
        "runtime_python": str(runtime / "python.exe"),
        "speaker": "Ryan",
        "language": "Portuguese",
        "instruct": "",
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, payload, model


def _save(manifest, payload):
    manifest.write_text(json.dumps(payload), encoding="utf-8")


def _fake_pcm(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x02" * 16000)


def test_no_artifact_preflight_fails_without_loading_package(tmp_path, monkeypatch):
    monkeypatch.setattr(qwen, "MODEL_ROOT", tmp_path)
    with pytest.raises(qwen.NeuralPreflightError, match="NEURAL_ARTIFACT_NOT_INSTALLED"):
        qwen.inspect_manifest(str(tmp_path / "no.json"))


@pytest.mark.parametrize("field,value,code", [
    ("source_model", "Other/Unreviewed", "NEURAL_MODEL_LICENSE_UNVERIFIED"),
    ("weights_license", "CC-BY-NC-4.0", "NEURAL_MODEL_LICENSE_UNVERIFIED"),
    ("weights_license_reviewed", False, "NEURAL_LICENSE_REVIEW_REQUIRED"),
    ("usage_scope", "commercial_publish", "NEURAL_LAB_SCOPE_REQUIRED"),
    ("speaker", "NOT_AN_OFFICIAL_SPEAKER", "NEURAL_SPEAKER_INVALID"),
    ("speaker", ["Ryan"], "NEURAL_SPEAKER_INVALID"),
    ("language", "pt-BR", "NEURAL_LANGUAGE_UNSUPPORTED"),
    ("instruct", "X" * 260, "NEURAL_INSTRUCTION_INVALID"),
    ("instruct", "Make it excited", "NEURAL_06B_INSTRUCTION_UNSUPPORTED"),
])
def test_metadata_gates(tmp_path, monkeypatch, field, value, code):
    manifest, payload, _ = _setup(tmp_path, monkeypatch)
    payload[field] = value
    _save(manifest, payload)
    with pytest.raises(qwen.NeuralPreflightError, match=code):
        qwen.inspect_manifest(str(manifest))


def test_missing_weights_fails_closed(tmp_path, monkeypatch):
    manifest, payload, model = _setup(tmp_path, monkeypatch)
    (model / "model.safetensors").unlink()
    with pytest.raises(qwen.NeuralPreflightError, match="NEURAL_WEIGHTS_INCOMPLETE"):
        qwen.inspect_manifest(str(manifest))


def test_external_path_rejected(tmp_path, monkeypatch):
    manifest, payload, _ = _setup(tmp_path, monkeypatch)
    payload["model_dir"] = str(tmp_path / "unapproved")
    _save(manifest, payload)
    with pytest.raises(qwen.NeuralPreflightError, match="NEURAL_PATH_NOT_ALLOWED"):
        qwen.inspect_manifest(str(manifest))


def test_no_runtime_python_fails_preflight(tmp_path, monkeypatch):
    manifest, payload, _ = _setup(tmp_path, monkeypatch)
    (tmp_path / "tools" / "python.exe").unlink()
    with pytest.raises(qwen.NeuralPreflightError, match="NEURAL_ARTIFACT_NOT_INSTALLED"):
        qwen.inspect_manifest(str(manifest))


def test_gameguard_halts_before_model_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(qwen, "game_active", lambda: True)
    config = TTSConfig(engine="qwen3", model=str(tmp_path / "missing.json"))
    with pytest.raises(qwen.NeuralPreflightError, match="GAMEGUARD_ACTIVE"):
        build_tts(config).synthesize("Bom dia.", tmp_path / "out.wav", config)
    assert not (tmp_path / "out.wav").exists()


def test_fake_worker_verifies_offline_args_and_atomic_wav(tmp_path, monkeypatch):
    manifest, payload, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(qwen, "game_active", lambda: False)
    invoked = []
    class Fake:
        def __init__(self, args, **kwargs):
            invoked.append((args, kwargs))
            request = json.loads(Path(args[3]).read_text(encoding="utf-8"))
            assert request["source_model"] == qwen.MODEL_ID
            assert request["speaker"] == "Ryan"
            _fake_pcm(request["output"])
            self.returncode = 0
        def communicate(self, timeout=None):
            return b"", b""
        def poll(self):
            return 0
    monkeypatch.setattr(qwen.subprocess, "Popen", Fake)
    config = TTSConfig(engine="qwen3", model=str(manifest))
    dest = tmp_path / "out.wav"
    dest.write_bytes(b"old")
    assert build_tts(config).synthesize("Bom dia.", dest, config) == dest
    with wave.open(str(dest), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 16000
    assert len(invoked) == 1
    args, kwargs = invoked[0]
    assert args[1] == "-I" and args[0].endswith("python.exe")
    assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
    assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert kwargs["env"]["CUDA_VISIBLE_DEVICES"] == ""
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert "HF_TOKEN" not in kwargs["env"]


def test_worker_failure_preserves_original_wav(tmp_path, monkeypatch):
    manifest, _, _ = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(qwen, "game_active", lambda: False)
    class Fake:
        returncode = 5
        def __init__(self, *a, **kw): pass
        def communicate(self, timeout=None): return b"", b""
        def poll(self): return 5
    monkeypatch.setattr(qwen.subprocess, "Popen", Fake)
    config = TTSConfig(engine="qwen3", model=str(manifest))
    dest = tmp_path / "existing.wav"
    dest.write_bytes(b"original")
    with pytest.raises(qwen.NeuralPreflightError, match="NEURAL_WORKER_FAILED"):
        build_tts(config).synthesize("Teste.", dest, config)
    assert dest.read_bytes() == b"original"


def test_gameguard_during_running_worker_kills_it(tmp_path, monkeypatch):
    manifest, _, _ = _setup(tmp_path, monkeypatch)
    checks = iter([False, True])
    monkeypatch.setattr(qwen, "game_active", lambda: next(checks))
    killed = []
    class Fake:
        returncode = None
        def __init__(self, *a, **kw): pass
        def communicate(self, timeout=None):
            if not killed: raise subprocess.TimeoutExpired("python", 3)
            return b"", b""
        def poll(self):
            return None if not killed else 1
        def kill(self):
            killed.append(True)
            self.returncode = 1
    monkeypatch.setattr(qwen.subprocess, "Popen", Fake)
    config = TTSConfig(engine="qwen3", model=str(manifest))
    with pytest.raises(qwen.NeuralPreflightError, match="GAMEGUARD_ACTIVE"):
        build_tts(config).synthesize("Teste.", tmp_path / "out.wav", config)
    assert killed
    assert not (tmp_path / "out.wav").exists()


def test_cli_missing_model_does_not_claim_success(tmp_path, capsys):
    code = cli_main(["audiobook", "--title", "Neural pilot",
                     "--chapters", '[{"text":"Uma frase."}]',
                     "--tts-engine", "qwen3",
                     "--tts-model", str(tmp_path / "missing.json"),
                     "--log-dir", str(tmp_path / "logs"),
                     "--registry", str(tmp_path / "history.db"),
                     str(tmp_path / "voice.wav")])
    assert code == 1
    printed = capsys.readouterr()
    assert "OK:" not in printed.out
    assert "ERRO:" in printed.err
    assert not (tmp_path / "voice.wav").exists()
