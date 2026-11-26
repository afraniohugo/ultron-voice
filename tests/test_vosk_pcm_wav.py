"""Regression for native and FFmpeg-normalized PCM, no network/model download."""
import shutil
import wave
import struct
import pytest
from backend.engine.asr.vosk_engine import VoskEngine


def make_wav(path, rate, channels):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(struct.pack("<h", 1000) * rate * channels)


def test_native_pcm_bypasses_ffmpeg(tmp_path):
    audio = tmp_path / "native.wav"
    make_wav(audio, 16000, 1)
    original = audio.read_bytes()
    pcm, rate = VoskEngine(models_dir=tmp_path)._read_pcm(str(audio))
    assert rate == 16000 and len(pcm) == 32000
    assert audio.read_bytes() == original


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg unavailable")
def test_normalization_creates_valid_wav_not_raw_pcm(tmp_path):
    audio = tmp_path / "stereo.wav"
    make_wav(audio, 24000, 2)
    original = audio.read_bytes()
    pcm, rate = VoskEngine(models_dir=tmp_path)._read_pcm(str(audio))
    assert rate == 16000 and len(pcm) == 32000
    assert audio.read_bytes() == original
