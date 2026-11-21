"""Audiobook pipeline: chapters -> per-chapter audio -> mixed audio.

Each chapter is either:
  * a text field that is synthesised to audio, or
  * an ``audio_path`` referencing an existing audio file that is reused.

All chapter tracks are concatenated into one mixed audio file.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import media
from .core.models import _utcnow
from .core.registry import Registry
from . import tts as tts_mod, sync

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


@dataclass
class AudiobookResult:
    output_path: Path
    checksums: dict = field(default_factory=dict)
    job_id: int | None = None
    exit_code: int = 0
    error: str | None = None


class AudiobookPipeline:
    """Turns a chapter list into a single mixed audio file."""

    def __init__(self, tts=None, registry: Registry | None = None, log=None) -> None:
        self.tts = tts or tts_mod.build_tts(
            tts_mod.TTSConfig(engine="piper", model="pt_BR-polyglot-medium")
        )
        self.registry = registry
        self.logger = log if log is not None else logger

    def run(self, job: AudiobookJob) -> AudiobookResult:
        job.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("audiobook: %s -> %s", job.title, job.output_path)
        try:
            chapter_files = self._render_chapters(job)
            if not chapter_files:
                return AudiobookResult(
                    output_path=job.output_path,
                    exit_code=1,
                    error="nenhum capitulo com audio ou texto",
                )
            mixed = job.output_path
            sync.concatenate_audios(chapter_files, mixed)
            chapters_json = json.dumps(job.chapters, ensure_ascii=False, sort_keys=True)
            checksums = {
                "input": hashlib.sha256(chapters_json.encode("utf-8")).hexdigest(),
                "output": media.sha256_file(mixed),
            }
            self._record(job, mixed, checksums, status="succeeded")
            return AudiobookResult(
                output_path=mixed,
                checksums=checksums,
                job_id=job.metadata.get("_id"),
                exit_code=0,
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("audiobook falhou")
            self._record(job, None, {"error": str(exc)}, status="failed")
            return AudiobookResult(output_path=job.output_path, exit_code=1, error=str(exc))

    def _render_chapters(self, job: AudiobookJob) -> list[Path]:
        rendered: list[Path] = []
        for i, ch in enumerate(job.chapters):
            text = ch.get("text") or ch.get("texto") or ""
            audio_path = ch.get("audio_path")
            if audio_path:
                src = Path(audio_path)
                if not src.exists():
                    raise FileNotFoundError(f"audio de capitulo nao encontrado: {src}")
                rendered.append(src.resolve())
                continue
            if not text:
                continue
            out = job.chunks_dir / f"ch_{i:03d}.wav"
            self.tts.synthesize(
                text,
                out,
                tts_mod.TTSConfig(engine=job.tts_engine, model=job.tts_model or tts_mod.TTSConfig().model),
            )
            rendered.append(out)
        return rendered

    def _record(self, job: AudiobookJob, output: Path | None, checksums: dict, status: str) -> None:
        out_path = output.as_posix() if output else ""
        entry = {
            "job_type": "audiobook",
            "status": status,
            "title": job.title,
            "language": job.language,
            "input_path": "",
            "output_path": out_path,
            "checksum_input": None,
            "checksum_output": checksums.get("output"),
            "errors": checksums.get("error"),
            "step": "audiobook",
            "started_at": job.created_at,
            "finished_at": _utcnow(),
            "metadata": {"tts_engine": job.tts_engine, "n_chapters": len(job.chapters)},
        }
        if self.registry:
            self.registry.record(**entry)


def audiobook(job: AudiobookJob, pipeline=None) -> AudiobookResult:
    pipe = pipeline if pipeline is not None else AudiobookPipeline()
    return pipe.run(job)
