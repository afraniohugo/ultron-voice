"""Contrato do audiobook WAV local, sem VoiceStudio, internet, GPU ou modelos."""
from __future__ import annotations

import hashlib
import json
import struct
import wave
from pathlib import Path

from ultron_voice import audiobook as audio_mod
from ultron_voice.audiobook import AudiobookJob, AudiobookPipeline, audiobook
from ultron_voice.cli import main
from ultron_voice.core.registry import Registry


def make_wav(path: Path, *, frames: int = 800, rate: int = 16000) -> Path:
    data = struct.pack("<h", 2000) * frames
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(data)
    return path


def test_native_two_chapter_wav_and_sha256(tmp_path):
    a = make_wav(tmp_path / "a.wav", frames=500)
    b = make_wav(tmp_path / "b.wav", frames=750)
    destination = tmp_path / "audios" / "livro.wav"
    registry = Registry(tmp_path / "history.db")
    try:
        result = audiobook(AudiobookJob(
            title="Livro local",
            chapters=[{"audio_path": str(a)}, {"audio_path": str(b)}],
            output_path=destination, registry=registry,
        ))
        assert result.exit_code == 0, result.error
        assert destination.is_file()
        with wave.open(str(destination), "rb") as recorded:
            assert recorded.getnframes() == 1250
            assert recorded.getframerate() == 16000
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == result.checksums["output"]
        assert registry.latest("audiobook")["status"] == "succeeded"
        assert result.job_id == registry.latest("audiobook")["id"]
        assert not list(destination.parent.glob(".ultron_voice_*"))
    finally:
        registry.close()


def test_empty_book_fails_without_writing_output(tmp_path):
    out = tmp_path / "empty.wav"
    result = audiobook(AudiobookJob("vazio", [], out))
    assert result.exit_code == 1
    assert "nenhum capitulo" in result.error
    assert not out.exists()


def test_incompatible_wav_preserves_previous_output(tmp_path):
    a = make_wav(tmp_path / "a.wav", rate=16000)
    b = make_wav(tmp_path / "b.wav", rate=8000)
    output = tmp_path / "livro.wav"
    output.write_bytes(b"original-safe")
    result = audiobook(AudiobookJob(
        "incompativel", [{"audio_path": str(a)}, {"audio_path": str(b)}], output))
    assert result.exit_code == 1
    assert "incompativeis" in result.error
    assert output.read_bytes() == b"original-safe"
    assert not list(tmp_path.glob(".ultron_voice_*"))


def test_text_chapter_uses_explicit_mock_tts_and_local_wav(tmp_path):
    class FakeTTS:
        calls = []
        def synthesize(self, text, target, config):
            self.calls.append((text, config.engine))
            return make_wav(target, frames=50)

    mock = FakeTTS()
    job = AudiobookJob("text-lab", [{"text": "Teste local."}], tmp_path / "tts.wav",
                       tts_engine="piper")
    result = AudiobookPipeline(tts=mock).run(job)
    assert result.exit_code == 0, result.error
    assert mock.calls == [("Teste local.", "piper")]


def test_cli_accepts_inline_json_and_reports_true_success(tmp_path, capsys):
    audio = make_wav(tmp_path / "frase.wav")
    out = tmp_path / "book.wav"
    command = [
        "audiobook", "--title", "Canario", "--chapters",
        json.dumps([{"audio_path": str(audio)}]),
        "--registry", str(tmp_path / "cli.db"),
        "--log-dir", str(tmp_path / "logs"),
        str(out),
    ]
    assert main(command) == 0
    assert out.exists()
    assert "sha256=" in capsys.readouterr().out


def test_cli_rejects_invalid_json_without_false_success(tmp_path, capsys):
    command = ["audiobook", "--title", "Canario", "--chapters", "{bad",
               "--log-dir", str(tmp_path / "logs"), str(tmp_path / "nope.wav")]
    assert main(command) == 1
    result = capsys.readouterr()
    assert "OK:" not in result.out
    assert "invalido" in result.err
    assert not (tmp_path / "nope.wav").exists()

def test_gameguard_blocks_synthesis_without_invoking_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_mod, "_game_active", lambda: True)
    class ForbiddenTTS:
        def synthesize(self, *args, **kwargs):
            raise AssertionError("TTS must not run while playing")
    output = tmp_path / "blocked.wav"
    result = AudiobookPipeline(tts=ForbiddenTTS()).run(
        AudiobookJob("gameguard", [{"text": "Aguardando."}], output))
    assert result.exit_code == 1
    assert "GAMEGUARD_ACTIVE" in result.error
    assert not output.exists()


def test_piper_requires_local_model_no_download(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_mod, "_game_active", lambda: False)
    output = tmp_path / "no_download.wav"
    result = audiobook(AudiobookJob(
        "sem-download", [{"text": "Teste."}], output,
        tts_engine="piper", tts_model="pt_BR-polyglot-medium"))
    assert result.exit_code == 1
    assert "PIPER_MODEL_LOCAL_REQUIRED" in result.error
    assert not output.exists()
