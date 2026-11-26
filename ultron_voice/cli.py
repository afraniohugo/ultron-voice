"""CLI: dub, audiobook, check-health, engines.

Entrypoint: ``ultron-voice`` (see pyproject.toml [project.scripts]).
Logging goes to stderr plus a log file under ``logs/``; a SHA-256 checksum
of every artifact is recorded in the registry (SQLite, ``history.db``).
"""

from __future__ import annotations

import argparse
import logging
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .core import health as health_mod
from .core import registry as core_registry
from . import dub, audiobook

logger = logging.getLogger("ultron-voice")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configure_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    fh = logging.FileHandler(log_dir / "ultron-voice.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)


def _build_registry(args) -> core_registry.Registry | None:
    raw = os.environ.get("ULTRON_VOICE_REGISTRY", args.registry)
    return core_registry.Registry(Path(raw)) if raw.strip() else core_registry.Registry()


def _cmd_dub(args) -> int:
    log_dir = Path(args.log_dir)
    _configure_logging(log_dir)
    job = dub.DubJob(
        title=args.title or Path(args.input).stem,
        input_path=Path(args.input),
        output_path=Path(args.output),
        language=args.language,
        engine=args.engine,
        tts_engine=args.tts_engine,
        subtitle=args.subtitle,
        section_duration=float(args.section_duration),
        chunks_dir=Path(args.chunks_dir),
        registry=_build_registry(args),
        source_extractor=None,
    )
    result = dub.dub(job)
    print(f"OK: {result.output_path}")
    if result.error:
        print(f"ERRO: {result.error}", file=sys.stderr)
        return 1
    return 0


def _cmd_audiobook(args) -> int:
    log_dir = Path(args.log_dir)
    _configure_logging(log_dir)
    try:
        if args.chapters_json:
            with Path(args.chapters_json).open("r", encoding="utf-8") as file:
                chapters = json.load(file)
        else:
            chapters = json.loads(args.chapters)
        if not isinstance(chapters, list) or not all(isinstance(ch, dict) for ch in chapters):
            raise ValueError("chapters deve ser lista de objetos")
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERRO: chapters JSON invalido: {exc}", file=sys.stderr)
        return 1
    job = audiobook.AudiobookJob(
        title=args.title,
        chapters=chapters,
        output_path=Path(args.output),
        language=args.language,
        tts_engine=args.tts_engine,
        tts_model=args.tts_model,
        registry=_build_registry(args),
    )
    result = audiobook.audiobook(job)
    if result.error:
        print(f"ERRO: {result.error}", file=sys.stderr)
        return 1
    print(f"OK: {result.output_path} | sha256={result.checksums.get('output', '')}")
    return 0


def _cmd_health(args) -> int:
    log_dir = Path(args.log_dir)
    _configure_logging(log_dir)
    report = health_mod.check_health()
    for k, v in report.items():
        logger.info("%s: %s", k, v)
    ok = all(report[k].get("ok") for k in report)
    return 0 if ok else 1


def _cmd_engines(args) -> int:
    log_dir = Path(args.log_dir)
    _configure_logging(log_dir)
    from .core.catalogue import translation_engines, tts_engines

    logger.info("tradutores disponiveis:")
    for eng in translation_engines():
        logger.info("%-10s %s", eng.name, eng.description)
    logger.info("motorias de voz disponiveis:")
    for eng in tts_engines():
        logger.info("%-10s %s", eng.name, eng.description)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ultron-voice", description="Ultron Voice: dublagem de video, audiobook e CLI/integracao/QA."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dub = sub.add_parser("dub", help="Pipeline dub (segment -> traduzir -> TTS -> sinc -> legenda)")
    p_dub.add_argument("input", help="audio ou video de entrada")
    p_dub.add_argument("output", help="diretorio/arquivo de saida")
    p_dub.add_argument("--title", help="titulo para o registo")
    p_dub.add_argument("--language", default="pt-BR")
    p_dub.add_argument("--engine", default="ollama", choices=["ollama", "argos"])
    p_dub.add_argument("--tts-engine", default="piper", choices=["piper", "espeak"])
    p_dub.add_argument("--tts-model", default="", help="modelo TTS (ex.: pt_BR-polyglot-medium)")
    p_dub.add_argument("--subtitle", action="store_true", default=True)
    p_dub.add_argument("--no-subtitle", dest="subtitle", action="store_false")
    p_dub.add_argument("--section-duration", type=float, default=15.0)
    p_dub.add_argument("--chunks-dir", default=".ultron_dub")
    p_dub.add_argument("--log-dir", default="logs")
    p_dub.add_argument("--registry", default=os.environ.get("ULTRON_VOICE_REGISTRY", ""))

    p_ab = sub.add_parser("audiobook", help="Audiobook: capitulos -> audio -> mix")
    p_ab.add_argument("--title", required=True)
    p_ab.add_argument("--chapters-json", help="caminho para JSON de capitulos (UTF-8)")
    p_ab.add_argument("--chapters", default="[]", help="JSON inline com capitulos [{texto, audio_path}]")
    p_ab.add_argument("--language", default="pt-BR")
    p_ab.add_argument("--tts-engine", default="piper", choices=["piper", "espeak", "sapi", "qwen3", "chatterbox_ptbr"])
    p_ab.add_argument("--tts-model", default="pt_BR-polyglot-medium")
    p_ab.add_argument("output", help="arquivo de audio final misto")
    p_ab.add_argument("--log-dir", default="logs")
    p_ab.add_argument("--registry", default=os.environ.get("ULTRON_VOICE_REGISTRY", ""))

    p_health = sub.add_parser("check-health", help="Verifica o ambiente (ffmpeg/ollama/argos/tts)")
    p_health.add_argument("--log-dir", default="logs")
    p_engines = sub.add_parser("engines", help="Lista os motores disponiveis")
    p_engines.add_argument("--log-dir", default="logs")

    p_asr = sub.add_parser("asr-stream", help="Local PCM16 mono 16kHz to incremental JSONL")
    source = p_asr.add_mutually_exclusive_group(required=True)
    source.add_argument("--wav", help="Local PCM WAV file")
    source.add_argument("--pcm-stdin", action="store_true", help="Raw PCM16 LE from stdin")
    p_asr.add_argument("--language", choices=["pt", "en"], default="pt")
    p_asr.add_argument("--idle-timeout", type=int, choices=range(1,31), default=10, metavar="1..30")
    p_asr.add_argument("--session-timeout", type=int, choices=range(5,181), default=150, metavar="5..180")

    return parser


def main(argv=None, *, dedicated_worker=False) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "asr-stream":
        from .asr_stream_cli import run, run_worker
        return run_worker(args) if dedicated_worker else run(args)
    handler = {
        "dub": _cmd_dub,
        "audiobook": _cmd_audiobook,
        "check-health": _cmd_health,
        "engines": _cmd_engines,
    }[args.command]
    return handler(args)


def console_main() -> int:
    return main(dedicated_worker=True)


if __name__ == "__main__":
    sys.exit(console_main())
