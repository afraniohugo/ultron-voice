"""Dub pipeline: segment -> translate -> TTS -> sync -> caption overlay.

Every stage is injectable so the pipeline is fully testable against local
fixtures without touching external services (translation/TTS engines).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import ffmpeg

from . import media
from .core.registry import Registry
from . import segment, sync, captions, translate as translate_mod, tts as tts_mod

logger = logging.getLogger("ultron-voice.dub")


@dataclass
class DubJob:
    input_path: Path
    output_path: Path
    language: str = "pt-BR"
    engine: str = "ollama"
    tts_engine: str = "piper"
    subtitle: bool = True
    section_duration: float = 15.0
    chunks_dir: Path = field(default_factory=lambda: Path("."))
    source_extractor = None  # injectable -> text per segment
    sync_fn = None
    caption_fn = None
    registry: Registry | None = None


@dataclass
class DubResult:
    output_path: Path
    checksums: dict = field(default_factory=dict)
    job_id: int | None = None
    exit_code: int = 0
    error: str | None = None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DubPipeline:
    """Orchestrates the five dubbing steps with injectable stages."""

    def __init__(
        self,
        *,
        source_extractor=None,
        translator=None,
        tts=None,
        sync_fn=None,
        caption_fn=None,
        registry: Registry | None = None,
        log=None,
    ) -> None:
        self.source_extractor = source_extractor
        self.translator = translator or translate_mod.build_translator
        self.tts = tts or tts_mod.build_tts
        self.sync_fn = sync_fn or sync.compose_dub_video
        self.caption_fn = caption_fn or captions.overlay_subtitles
        self.registry = registry
        self.logger = log if log is not None else logger

    # -- pipeline -----------------------------------------------------------
    def run(self, job: DubJob) -> DubResult:
        job.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("iniciando dub: %s -> %s", job.input_path, job.output_path)
        try:
            segments = self._segment(job)
            synth = self._synthesize(job, segments)
            final_audio = self._sync(job, segments, synth)
            final_audio = self._caption(job, segments, final_audio)
            checksums = {
                "input": media.sha256_file(job.input_path),
                "output": media.sha256_file(final_audio),
            }
            self._record(job, final_audio, checksums, status="succeeded")
            return DubResult(
                output_path=final_audio,
                checksums=checksums,
                job_id=job.metadata.get("_id"),
                exit_code=0,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("dub falhou")
            self._record(job, None, {"error": str(exc)}, status="failed")
            return DubResult(output_path=job.output_path, exit_code=1, error=str(exc))

    def _segment(self, job: DubJob) -> list[segment.Segment]:
        return segment.segment_audio_fixed(
            job.input_path, job.chunks_dir, duration=job.section_duration
        )

    def _synthesize(self, job: DubJob, segments: list[segment.Segment]) -> list[Path]:
        config_t = translate_mod.TranslateConfig(
            engine=job.engine, source_lang=job.language, target_lang="en-US"
        )
        translator = self.translator(config_t)
        tts_instance = self.tts()
        synth: list[Path] = []
        for seg in segments:
            text = self._source_text(job, seg)
            translated = translator.translate(text, config_t)
            out_audio = job.chunks_dir / f"synth_{seg.index:03d}.wav"
            tts_instance.synthesize(translated, out_audio, tts_mod.TTSConfig(engine=job.tts_engine))
            synth.append(out_audio)
        return synth

    def _source_text(self, job: DubJob, seg: segment.Segment) -> str:
        if self.source_extractor:
            return str(self.source_extractor(str(seg.path)))
        raise RuntimeError(
            "source_extractor nao configurado (STT) para extrair o audio original"
        )

    def _sync(self, job: DubJob, segments: list[segment.Segment], synth: list[Path]) -> Path:
        total_audio = job.chunks_dir / "dubbed.wav"
        sync.concatenate_audios(synth, total_audio)
        pieces = []
        for seg, pa in zip(segments, synth):
            padded_seg = pa.with_suffix(".pad.wav")
            sync.pad_audio_to_duration(pa, padded_seg, seg.end - seg.start)
            pieces.append(padded_seg)
        sync.concatenate_audios(pieces, job.chunks_dir / "dubbed_padded.wav")
        return self.sync_fn(job.input_path, job.chunks_dir / "dubbed_padded.wav", job.output_path.with_suffix(".mp4"))

    def _caption(self, job: DubJob, segments: list[segment.Segment], audio: Path) -> Path:
        caps = [
            captions.Caption(i, seg.start, seg.end, f"[{i + 1}]")
            for i, seg in enumerate(segments)
        ]
        srt = captions.build_subtitles(segments, caps)
        final_video = job.output_path.with_suffix(".mp4")
        return self.caption_fn(job.input_path, srt, final_video)

    # -- registry -----------------------------------------------------------
    def _record(self, job: DubJob, output: Path | None, checksums: dict, status: str) -> None:
        out_path = output.as_posix() if output else ""
        entry = {
            "job_type": "dub",
            "status": status,
            "title": job.title,
            "language": job.language,
            "input_path": job.input_path.as_posix(),
            "output_path": out_path,
            "checksum_input": checksums.get("input"),
            "checksum_output": checksums.get("output"),
            "errors": checksums.get("error"),
            "step": "dub",
            "started_at": job.created_at,
            "finished_at": _utcnow(),
            "metadata": {
                "engine": job.engine,
                "tts_engine": job.tts_engine,
                "subtitle": job.subtitle,
            },
        }
        if self.registry:
            self.registry.record(**entry)


def dub(job: DubJob, pipeline=None) -> DubResult:
    """Convenience entrypoint: build a pipeline and run one job."""
    pipe = pipeline if pipeline is not None else DubPipeline()
    return pipe.run(job)
