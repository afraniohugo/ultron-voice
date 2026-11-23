"""F5 short-phrase batch: one local Chatterbox model load, no daemon/GPU.

Unit/fake subprocess tests; actual CPU benchmark is separate and logged.
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import pytest

from ultron_voice import chatterbox_batch as batch
from ultron_voice import audiobook as audio
from ultron_voice.tts import TTSConfig


def pcm(path, nframes=8000):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\x02\x00" * nframes)


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "game_active", lambda: False)
    settings = {
        "status": "READY_FOR_ISOLATED_CHATTR_PTBR", "scope": "laboratory_only",
        "runtime_python": str(tmp_path / "python.exe"),
        "model_dir": str(tmp_path / "weights"),
        "source_dir": str(tmp_path / "source"),
        "reference_audio": str(tmp_path / "synthetic.wav"),
        "language": "pt", "temperature": .8,
        "exaggeration": .55, "cfg_weight": .4,
    }
    monkeypatch.setattr(batch, "inspect_manifest", lambda name: settings)
    return TTSConfig(engine="chatterbox_ptbr", model="manifest.json")


@pytest.mark.parametrize("texts,outputs,code", [
    ([], [], "CHATTERBOX_BATCH_SIZE_INVALID"),
    (["a"], ["a.wav"], "CHATTERBOX_BATCH_SIZE_INVALID"),
    (["a", "b"], ["a.wav"], "CHATTERBOX_BATCH_SIZE_INVALID"),
    (["a", "b"], ["a.wav", "a.wav"], "CHATTERBOX_BATCH_OUTPUT_INVALID"),
    ([" ", "a"], ["a.wav", "b.wav"], "CHATTERBOX_BATCH_TEXT_INVALID"),
    (["a" * 280, "b" * 280, "c"], ["a.wav", "b.wav", "c.wav"], None),
    (["a" * 280, "b" * 280, "c" * 50], ["a.wav", "b.wav", "c.wav"], "CHATTERBOX_BATCH_TEXT_INVALID"),
    (["a", "b"], ["a.mp3", "b.wav"], "CHATTERBOX_BATCH_OUTPUT_INVALID"),
])
def test_batch_input_gates(tmp_path, monkeypatch, texts, outputs, code):
    cfg = setup(tmp_path, monkeypatch)
    if code is None:
        return  # 561 characters is within the explicit 600-char policy.
    with pytest.raises(ValueError, match=code):
        batch.ChatterboxBatchTTS().synthesize_many(
            texts, [tmp_path / p for p in outputs], cfg)


def test_fake_worker_one_process_two_clips_tokens_and_atomic_wavs(tmp_path, monkeypatch):
    cfg = setup(tmp_path, monkeypatch)
    monkeypatch.setenv("HF_TOKEN", "SECRET")
    monkeypatch.setenv("OPENAI_API_KEY", "SECRET")
    created = []
    class Fake:
        returncode = 0
        def __init__(self, args, **kwargs):
            created.append((args, kwargs))
            payload = json.loads(Path(args[3]).read_text(encoding="utf-8"))
            assert len(payload["items"]) == 2
            assert [x["text"] for x in payload["items"]] == ["Olá.", "Bom dia."]
            for index, item in enumerate(payload["items"]):
                pcm(item["output"], nframes=8000 + index)
        def communicate(self, timeout=None): return b"", b""
        def poll(self): return 0
    monkeypatch.setattr(batch.subprocess, "Popen", Fake)
    paths = [tmp_path / "1.wav", tmp_path / "2.wav"]
    for path in paths:
        path.write_bytes(b"before")
    assert batch.ChatterboxBatchTTS().synthesize_many(
        ["Olá.", "Bom dia."], paths, cfg) == paths
    assert len(created) == 1
    args, opts = created[0]
    assert args[1] == "-I"
    assert opts["env"]["HF_HUB_OFFLINE"] == "1"
    assert opts["env"]["CUDA_VISIBLE_DEVICES"] == ""
    assert "HF_TOKEN" not in opts["env"]
    assert "OPENAI_API_KEY" not in opts["env"]
    with wave.open(str(paths[0]), "rb") as f:
        assert f.getnframes() == 8000
    with wave.open(str(paths[1]), "rb") as f:
        assert f.getnframes() == 8001


def test_worker_error_preserves_existing_wavs(tmp_path, monkeypatch):
    cfg = setup(tmp_path, monkeypatch)
    class Fake:
        returncode = 5
        def __init__(self, *args, **kwargs): pass
        def communicate(self, timeout=None): return b"", b""
        def poll(self): return 5
    monkeypatch.setattr(batch.subprocess, "Popen", Fake)
    paths = [tmp_path / "1.wav", tmp_path / "2.wav"]
    for path in paths:
        path.write_bytes(b"keep")
    with pytest.raises(batch.ChatterboxPreflightError, match="BATCH_WORKER_FAILED"):
        batch.ChatterboxBatchTTS().synthesize_many(["a", "b"], paths, cfg)
    assert [p.read_bytes() for p in paths] == [b"keep", b"keep"]


def test_gameguard_during_job_kills_process(tmp_path, monkeypatch):
    cfg = setup(tmp_path, monkeypatch)
    state = iter([False, True])
    monkeypatch.setattr(batch, "game_active", lambda: next(state))
    killed = []
    class Fake:
        returncode = None
        def __init__(self, *args, **kwargs): pass
        def communicate(self, timeout=None):
            if not killed:
                raise subprocess.TimeoutExpired("python", 3)
            return b"", b""
        def poll(self): return None if not killed else 1
        def kill(self): killed.append(True); self.returncode = 1
    monkeypatch.setattr(batch.subprocess, "Popen", Fake)
    with pytest.raises(batch.ChatterboxPreflightError, match="GAMEGUARD_ACTIVE"):
        batch.ChatterboxBatchTTS().synthesize_many(
            ["a", "b"], [tmp_path / "a.wav", tmp_path / "b.wav"], cfg)
    assert killed and not (tmp_path / "a.wav").exists()


def test_wrong_format_does_not_replace_existing_wavs(tmp_path, monkeypatch):
    cfg = setup(tmp_path, monkeypatch)
    class Fake:
        returncode = 0
        def __init__(self, args, **kwargs):
            request = json.loads(Path(args[3]).read_text(encoding="utf-8"))
            pcm(request["items"][0]["output"])
            with wave.open(request["items"][1]["output"], "wb") as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                wav.writeframes(b"\0\0" * 20)
        def communicate(self, timeout=None): return b"", b""
        def poll(self): return 0
    monkeypatch.setattr(batch.subprocess, "Popen", Fake)
    paths = [tmp_path / "a.wav", tmp_path / "b.wav"]
    for p in paths: p.write_bytes(b"original")
    with pytest.raises(batch.ChatterboxPreflightError, match="BATCH_MISMATCH_FORMAT"):
        batch.ChatterboxBatchTTS().synthesize_many(["a", "b"], paths, cfg)
    assert all(p.read_bytes() == b"original" for p in paths)


def test_audiobook_two_chapters_one_batch_and_original_order(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "_game_active", lambda: False)
    calls = []
    def fake(self, texts, outputs, config):
        calls.append(texts)
        for i, p in enumerate(outputs):
            pcm(p, 100 + i)
        return outputs
    monkeypatch.setattr(batch.ChatterboxBatchTTS, "synthesize_many", fake)
    dest = tmp_path / "final.wav"
    job = audio.AudiobookJob(
        title="F5 test", chapters=[{"text":"Primeiro."},{"text":"Segundo."}],
        output_path=dest, tts_engine="chatterbox_ptbr",
        tts_model="test-manifest",
    )
    res = audio.AudiobookPipeline().run(job)
    assert res.exit_code == 0 and calls == [["Primeiro.", "Segundo."]]
    with wave.open(str(dest), "rb") as wav:
        assert wav.getnframes() == 201
    assert len(res.checksums["output"]) == 64


def test_mixed_audio_and_text_does_not_route_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "_game_active", lambda: False)
    calls = []
    def wrong(self, texts, outputs, config):
        calls.append("batch")
        raise AssertionError("Mixed input cannot be batch")
    monkeypatch.setattr(batch.ChatterboxBatchTTS, "synthesize_many", wrong)
    from ultron_voice import tts
    class FakeTTS:
        def synthesize(self, text, path, cfg):
            pcm(path)
    source = tmp_path / "source.wav"
    pcm(source)
    target = tmp_path / "mixed.wav"
    job = audio.AudiobookJob(
        title="mixed", chapters=[{"audio_path":str(source)},{"text":"Olá."}],
        output_path=target, tts_engine="chatterbox_ptbr",
    )
    assert audio.AudiobookPipeline(tts=FakeTTS()).run(job).exit_code == 0
    assert not calls
