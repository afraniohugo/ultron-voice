"""F6 brand-pronunciation lab regressions: no neural runtime needed."""
from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path

import pytest

from ultron_voice import pronunciation_lab as lab


def _wav(path: Path, *, rate=24000, nframes=1200):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\x04\x00" * nframes)


def test_three_variants_explicit_original_and_accents():
    items = lab.variants("Eu sou o Ultron. Olá!")
    assert [item["id"] for item in items] == [
        "original", "first_syllable", "last_syllable"]
    assert [item["text"] for item in items] == [
        "Eu sou o Ultron. Olá!", "Eu sou o Últron. Olá!",
        "Eu sou o Ultrôn. Olá!"]


def test_only_exact_word_is_replaced():
    for text in ("MegUltron", "UltronPlus", "Ultron_foo", "ULTRON", "ultron"):
        with pytest.raises(ValueError, match="ONE_EXACT_BRAND_REQUIRED"):
            lab.variants(text)


@pytest.mark.parametrize("bad", ["", "Sem marca.", "Ultron e Ultron.", "Ultron\nfim", "Ultron" + "a" * 170])
def test_invalid_brand_text_fails_closed(bad):
    with pytest.raises(ValueError, match="ULTRON_LAB_"):
        lab.variants(bad)


def test_assembly_preserves_pcm_and_silence(tmp_path):
    clips = [tmp_path / f"trial_{i}.wav" for i in range(3)]
    for path in clips: _wav(path, nframes=2400)
    out = tmp_path / "mixed.wav"
    result = lab.assemble_clips(clips, out, pause_ms=500)
    with wave.open(str(out), "rb") as final:
        assert final.getframerate() == 24000
        assert final.getnframes() == 3 * 2400 + 2 * 12000
    assert result["duration_segments_seconds"] == [.1, .1, .1]
    assert result["comparison_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError, match="OUTPUT_EXISTS"):
        lab.assemble_clips(clips, out)


def test_assembly_blocks_mismatched_pcm(tmp_path):
    tracks = [tmp_path / f"{i}.wav" for i in range(3)]
    for index, track in enumerate(tracks):
        _wav(track, rate=16000 if index == 1 else 24000)
    result = tmp_path / "reject.wav"
    with pytest.raises(ValueError, match="WAV_FORMAT_MISMATCH"):
        lab.assemble_clips(tracks, result)
    assert not result.exists()


def test_run_lab_requires_canonical_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "LOG_ROOT", tmp_path)
    with pytest.raises(lab.ChatterboxPreflightError, match="OUTPUT_NOT_ALLOWED"):
        lab.run_lab(lab.DEFAULT_TEXT, "unused", str(tmp_path / "wrong"))


def test_run_lab_single_batch_and_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "LOG_ROOT", tmp_path)
    monkeypatch.setattr(lab, "game_active", lambda: False)
    out = tmp_path / "pronunciation_f6_20261122"
    called = []
    def fake(self, texts, outputs, config):
        called.append((texts, config.engine))
        for idx, path in enumerate(outputs):
            _wav(path, nframes=idx + 900)
        return outputs
    monkeypatch.setattr(lab.ChatterboxBatchTTS, "synthesize_many", fake)
    result = lab.run_lab(lab.DEFAULT_TEXT, "manifest", str(out))
    assert len(called) == 1 and called[0][1] == "chatterbox_ptbr"
    assert len(result["trial_variants"]) == 3
    assert result["canonical_text"] == lab.DEFAULT_TEXT
    receipt = out / "pronunciation_lab_receipt.json"
    assert receipt.is_file()
    assert json.loads(receipt.read_text(encoding="utf-8")) == result
    assert (out / "comparison_ultron_3_variants.wav").is_file()
    with pytest.raises(lab.ChatterboxPreflightError, match="ALREADY_EXECUTED"):
        lab.run_lab(lab.DEFAULT_TEXT, "manifest", str(out))




def test_game_started_after_synthesis_blocks_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "LOG_ROOT", tmp_path)
    monkeypatch.setattr(lab, "game_active", lambda: True)
    out = tmp_path / "pronunciation_f6_20261122"
    def fake(self, texts, outputs, config):
        for path in outputs:
            _wav(path)
        return outputs
    monkeypatch.setattr(lab.ChatterboxBatchTTS, "synthesize_many", fake)
    with pytest.raises(lab.ChatterboxPreflightError, match="GAMEGUARD_ACTIVE"):
        lab.run_lab(lab.DEFAULT_TEXT, "manifest", str(out))
    assert not (out / "comparison_ultron_3_variants.wav").exists()
    assert not (out / "pronunciation_lab_receipt.json").exists()


def test_cannot_synthesize_outside_lab(tmp_path, monkeypatch):
    monkeypatch.setattr(lab, "LOG_ROOT", tmp_path)
    other = tmp_path.parent / "escape_path"
    with pytest.raises(lab.ChatterboxPreflightError, match="OUTPUT_NOT_ALLOWED"):
        lab.run_lab(lab.DEFAULT_TEXT, "manifest", str(other))
