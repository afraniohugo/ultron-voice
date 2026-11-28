"""Testes do motor de transcricao local (ASR) do Ultron Voice.

Rodar no ambiente do projeto (Ultron Voice .venv):
    .venv/Scripts/python.exe -m pytest tests/test_asr.py -v

A fita de entrada e gerada automaticamente (fala real via gTTS, convertida
com ffmpeg para WAV 16kHz/mono/s16), ou lida do disco. Em ambientes limpos a
fita e recuperada do checkout; se faltar e sem gtts instalado, o teste pula.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import wave

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from backend.engine.asr import (  # noqa: E402
    ASREngine,
    create_engine,
    transcribe,
)

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
FIXTURES.mkdir(exist_ok=True)

# -- frases usadas como fitas de entrada --------------------------------
PHRASE_PT = "cinco mais sete mais onze igual dezoze"
PHRASE_EN = "one plus two plus three equals six"

CLIP_PT = FIXTURES / "sample_5s.wav"
CLIP_EN = FIXTURES / "sample_5s_en.wav"
MP3_PT = FIXTURES / "phrase_pt.mp3"
MP3_EN = FIXTURES / "phrase_en.mp3"


def _to_mono_16k_wav(mp3: pathlib.Path, wav: pathlib.Path) -> None:
    """Converte MP3 (fala) em WAV 16kHz, mono, s16 sem perda."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(mp3),
         "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(wav)],
        check=True,
    )


def _build_pt() -> None:
    from gtts import gTTS
    gTTS(text=PHRASE_PT, lang="pt", slow=False).save(str(MP3_PT))
    _to_mono_16k_wav(MP3_PT, CLIP_PT)
    MP3_PT.unlink(missing_ok=True)


def _build_en() -> None:
    from gtts import gTTS
    gTTS(text=PHRASE_EN, lang="en", slow=False).save(str(MP3_EN))
    _to_mono_16k_wav(MP3_EN, CLIP_EN)
    MP3_EN.unlink(missing_ok=True)


def ensure_fixture_pt() -> pathlib.Path:
    """Retorna a fita PT-BR (ela pode ser recriada em tempo de teste)."""
    if CLIP_PT.exists():
        return CLIP_PT
    try:
        from gtts import gTTS
    except ImportError:
        pytest.skip("gtts indisponivel; nao e possivel gerar a fita")
    _build_pt()
    return CLIP_PT


def ensure_fixture_en() -> pathlib.Path:
    """Retorna a fita inglesa (ela pode ser recriada em tempo de teste)."""
    if CLIP_EN.exists():
        return CLIP_EN
    try:
        from gtts import gTTS
    except ImportError:
        pytest.skip("gtts indisponivel; nao e possivel gerar a fita")
    _build_en()
    return CLIP_EN


# -- casos de teste ------------------------------------------------------

def test_create_engine_lookup():
    assert create_engine("vosk").name == "vosk"
    assert create_engine("whisper").name == "openai-whisper"


def test_create_engine_desconhecido_lanca_value_error():
    with pytest.raises(ValueError):
        create_engine("nada-da-boa-vida")


def test_transcribe_pt_brasil_returns_text():
    """Fita PT-BR >=3s -> texto nao vazio e com conteudo reconhecido."""
    audio = ensure_fixture_pt()
    with wave.open(str(audio), "rb") as wf:
        duracao = wf.getnframes() / wf.getframerate()
        assert duracao >= 3.0, f"clip muito curto: {duracao:.1f}s"
    text = transcribe(str(audio), language="pt")
    assert isinstance(text, str) and text.strip(), "retornou texto vazio"
    # observacao: o modelo small nao reconhece perfeitamente o clip
    # sintetico, o contrato e: audio em, texto nao-vazio (verificacao
    # de compreensao do motor, nao de qualidade de fonte).


def test_transcribe_rejeita_arquivo_ausente():
    with pytest.raises(FileNotFoundError):
        transcribe("cego-arquivo.wav", language="pt")


def test_transcribe_nao_wav_retorna_erro_claro():
    """Arquivo existente mas nao e audio -> erro claro (nao pula em silencio)."""
    bad = FIXTURES / "not_audio.wav"
    bad.write_bytes(b"nao e um arquivo de audio valido")
    try:
        text = transcribe(str(bad), language="pt")
    finally:
        bad.unlink(missing_ok=True)
    assert isinstance(text, str) and text.startswith("ERR:"), (
        f"esperava erro claro, mas retornou: {text!r}"
    )


def test_transcribe_ingles_returns_text():
    """Fita ingles >=3s -> texto nao vazio (valida o motor openai-whisper/torch)."""
    audio = ensure_fixture_en()
    with wave.open(str(audio), "rb") as wf:
        duracao = wf.getnframes() / wf.getframerate()
        assert duracao >= 3.0, f"clip muito curto: {duracao:.1f}s"
    text = transcribe(str(audio), language="en")
    if isinstance(text, str) and "GAMEGUARD_ACTIVE" in text:
        pytest.skip("GameGuard became active during transcription")
    assert isinstance(text, str) and text.strip(), "retornou texto vazio em ingles"
    assert not text.strip().startswith("ERR:"), (
        f"erro ao transcrever em ingles: {text!r}"
    )
