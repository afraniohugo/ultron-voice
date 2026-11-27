"""Audiobook local: concatena capítulos WAV sem VoiceStudio, rede ou GPU.

O caminho PCM exige WAV sem compressao e parâmetros idênticos. Síntese de
texto usa apenas o TTS local explicitamente configurado (quando disponível).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path

from . import media
from .core.models import _utcnow
from .core.registry import Registry
from . import tts as tts_mod
from .gameguard import game_active as _game_active

logger = logging.getLogger("ultron-voice.audiobook")


@dataclass
class AudiobookJob:
    title: str
    chapters: list[dict]
    output_path: Path
    language: str = "pt-BR"
    tts_engine: str = "piper"
    tts_model: str = ""
    registry: Registry | None = None
    created_at: str = field(default_factory=_utcnow)


@dataclass
class AudiobookResult:
    output_path: Path
    checksums: dict = field(default_factory=dict)
    job_id: int | None = None
    exit_code: int = 0
    error: str | None = None


def concatenate_pcm_wavs(paths: list[Path], output_path: Path) -> None:
    """Concatenação PCM em streaming, sem FFmpeg e sem conversão silenciosa."""
    if not paths:
        raise ValueError("nenhum audio para concatenar")
    expected = None
    with wave.open(str(output_path), "wb") as dest:
        for src in paths:
            if src.suffix.lower() != ".wav":
                raise ValueError("somente arquivos WAV PCM sao aceitos nesta etapa")
            with wave.open(str(src), "rb") as track:
                fmt = (track.getnchannels(), track.getsampwidth(),
                       track.getframerate(), track.getcomptype())
                if fmt[-1] != "NONE":
                    raise ValueError("WAV comprimido nao suportado")
                if expected is None:
                    expected = fmt
                    dest.setnchannels(fmt[0])
                    dest.setsampwidth(fmt[1])
                    dest.setframerate(fmt[2])
                elif expected != fmt:
                    raise ValueError("formatos WAV incompativeis; conversao explicita necessaria")
                while True:
                    block = track.readframes(4096)
                    if not block:
                        break
                    dest.writeframesraw(block)


class AudiobookPipeline:
    """Gerador nativo de audiobook; grava saida final somente apos QA basico."""

    def __init__(self, tts=None, registry: Registry | None = None, log=None) -> None:
        self.tts = tts
        self.registry = registry
        self.logger = log if log is not None else logger

    def run(self, job: AudiobookJob) -> AudiobookResult:
        output = Path(job.output_path)
        temp_output = None
        try:
            if output.suffix.lower() != ".wav":
                raise ValueError("saída nativa deve ter extensão .wav")
            if not isinstance(job.chapters, list):
                raise ValueError("chapters deve ser uma lista JSON")
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="ultron_voice_", dir=output.parent) as tmp:
                chunks_dir = Path(tmp)
                tracks = self._render_chapters(job, chunks_dir)
                if not tracks:
                    raise ValueError("nenhum capitulo com audio ou texto")
                fd, name = tempfile.mkstemp(prefix=".ultron_voice_", suffix=".wav", dir=output.parent)
                os.close(fd)
                temp_output = Path(name)
                concatenate_pcm_wavs(tracks, temp_output)
                with wave.open(str(temp_output), "rb") as wav:
                    if wav.getnframes() == 0:
                        raise ValueError("audiobook gerado sem frames")
                checksum = media.sha256_file(temp_output)
                os.replace(temp_output, output)
                temp_output = None

            checksum_input = hashlib.sha256(
                json.dumps(job.chapters, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            job_id = self._record(job, output, checksum_input, checksum, None, "succeeded")
            return AudiobookResult(
                output_path=output,
                checksums={"input": checksum_input, "output": checksum},
                job_id=job_id,
            )
        except Exception as exc:
            self.logger.warning("audiobook local falhou: %s", type(exc).__name__)
            try:
                self._record(job, None, None, None, str(exc), "failed")
            except Exception:
                self.logger.exception("falha ao registrar erro de audiobook")
            return AudiobookResult(output_path=output, exit_code=1, error=str(exc))
        finally:
            if temp_output is not None:
                temp_output.unlink(missing_ok=True)

    def _render_chapters(self, job: AudiobookJob, chunks_dir: Path) -> list[Path]:
        # Small text-only audiobook jobs use one Chatterbox model load for all
        # fragments. No persistent service, GPU or changed audio-path behavior.
        if (self.tts is None and job.tts_engine == "chatterbox_ptbr" and
                2 <= len(job.chapters) <= 4 and
                all(isinstance(ch, dict) and not ch.get("audio_path") and
                    isinstance(ch.get("text") or ch.get("texto"), str)
                    for ch in job.chapters)):
            from .chatterbox_batch import ChatterboxBatchTTS, MAX_TOTAL_CHARS
            texts = [ch.get("text") or ch.get("texto") for ch in job.chapters]
            if sum(len(t) for t in texts) <= MAX_TOTAL_CHARS:
                if _game_active():
                    raise RuntimeError("GAMEGUARD_ACTIVE: TTS pausado durante jogo")
                cfg = tts_mod.TTSConfig(
                    engine=job.tts_engine,
                    model=job.tts_model or tts_mod.TTSConfig().model,
                )
                targets = [chunks_dir / f"ch_{i:03d}.wav"
                           for i in range(len(texts))]
                return ChatterboxBatchTTS().synthesize_many(texts, targets, cfg)
        tracks = []
        for index, chapter in enumerate(job.chapters):
            if not isinstance(chapter, dict):
                raise ValueError("cada capitulo deve ser um objeto")
            audio_path = chapter.get("audio_path")
            text = chapter.get("text") or chapter.get("texto")
            if audio_path and text:
                raise ValueError("capitulo deve ter audio_path ou text, nao ambos")
            if audio_path:
                src = Path(audio_path)
                if not src.is_file():
                    raise FileNotFoundError(f"audio de capitulo nao encontrado: {src}")
                tracks.append(src)
            elif text:
                if not isinstance(text, str):
                    raise ValueError("texto do capitulo invalido")
                if _game_active():
                    raise RuntimeError("GAMEGUARD_ACTIVE: TTS pausado durante jogo")
                if job.tts_engine not in {"piper", "espeak", "sapi", "qwen3", "chatterbox_ptbr"}:
                    raise ValueError("engine TTS desconhecida")
                if self.tts is None and job.tts_engine == "piper":
                    model = Path(job.tts_model)
                    if not model.is_absolute() or not model.is_file() or model.suffix.lower() != ".onnx":
                        raise RuntimeError("PIPER_MODEL_LOCAL_REQUIRED: modelo .onnx instalado deve ser informado")
                cfg = tts_mod.TTSConfig(
                    engine=job.tts_engine,
                    model=job.tts_model or tts_mod.TTSConfig().model,
                )
                tts = self.tts or tts_mod.build_tts(cfg)
                target = chunks_dir / f"ch_{index:03d}.wav"
                tts.synthesize(text, target, cfg)
                if not target.is_file():
                    raise RuntimeError("TTS local nao produziu WAV")
                tracks.append(target)
        return tracks

    def _record(self, job: AudiobookJob, output: Path | None,
                checksum_input: str | None, checksum_output: str | None,
                error: str | None, status: str) -> int | None:
        registry = job.registry or self.registry
        if registry is None:
            return None
        return registry.record(
            job_type="audiobook", status=status, title=job.title,
            language=job.language, input_path="",
            output_path=str(output) if output else "",
            checksum_input=checksum_input,
            checksum_output=checksum_output, errors=error, step="audiobook",
            started_at=job.created_at, finished_at=_utcnow(),
            metadata={"tts_engine": job.tts_engine, "n_chapters": len(job.chapters)},
        )


def audiobook(job: AudiobookJob, pipeline=None) -> AudiobookResult:
    pipe = pipeline if pipeline is not None else AudiobookPipeline()
    return pipe.run(job)
