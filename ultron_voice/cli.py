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
    path = Path(os.environ.get("ULTRON_VOICE_REGISTRY", args.registry))
    return core_registry.Registry(path) if path else None


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
    chapters = args.chapters
    if args.chapters_json:
        try:
            chapters = json.load(args.chapters_json)
        except Exception as exc:  # noqa: BLE001
            print(f"ERRO: invalid chapters JSON: {exc}", file=sys.stderr)
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
    print(f"OK: {result.output_path}")
    if result.error:
        print(f"ERRO: {result.error}", file=sys.stderr)
        return 1
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
    p_ab.add_argument("--chapters-json", type=argparse.FileType("r"), help="arquivo JSON com a lista de capitulos")
    p_ab.add_argument("--chapters", default="[]", help="JSON inline com capitulos [{texto, audio_path}]")
    p_ab.add_argument("--language", default="pt-BR")
    p_ab.add_argument("--tts-engine", default="piper")
    p_ab.add_argument("--tts-model", default="pt_BR-polyglot-medium")
    p_ab.add_argument("output", help="arquivo de audio final misto")
    p_ab.add_argument("--log-dir", default="logs")
    p_ab.add_argument("--registry", default=os.environ.get("ULTRON_VOICE_REGISTRY", ""))

    p_health = sub.add_parser("check-health", help="Verifica o ambiente (ffmpeg/ollama/argos/tts)")
    p_health.add_argument("--log-dir", default="logs")
    p_engines = sub.add_parser("engines", help="Lista os motores disponiveis")
    p_engines.add_argument("--log-dir", default="logs")

    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = {
        "dub": _cmd_dub,
        "audiobook": _cmd_audiobook,
        "check-health": _cmd_health,
        "engines": _cmd_engines,
    }[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
