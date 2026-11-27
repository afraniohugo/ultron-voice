"""F6 isolated pronunciation experiments for the name Ultron.

This is an EXPLICIT laboratory experiment, not a production pronunciation
rewrite. Original text is preserved in records; brand is never silently changed.
Chatterbox PTBR weights, synthetic reference and GameGuard gates are reused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .chatterbox_batch import ChatterboxBatchTTS
from .chatterbox_ptbr import ChatterboxPreflightError, LOG_ROOT
from .gameguard import game_active
from .tts import TTSConfig

BRAND = re.compile(r"(?<!\w)Ultron(?!\w)", flags=re.UNICODE)
TRIALS = (
    ("original", "Ultron"),
    ("first_syllable", "Últron"),
    ("last_syllable", "Ultrôn"),
)
DEFAULT_TEXT = "Olá! Eu sou o Ultron. Estou pronto para ajudar."
MAX_CHARS = 170


def variants(text: str) -> list[dict[str, str]]:
    if not isinstance(text, str) or not text or len(text) > MAX_CHARS:
        raise ValueError("ULTRON_LAB_TEXT_INVALID")
    if len(BRAND.findall(text)) != 1:
        raise ValueError("ULTRON_LAB_ONE_EXACT_BRAND_REQUIRED")
    if any(ord(ch) < 32 for ch in text):
        raise ValueError("ULTRON_LAB_CONTROL_CHARACTERS")
    items = [{"id": slug, "text": BRAND.sub(pronunciation, text)}
             for slug, pronunciation in TRIALS]
    if len({item["text"] for item in items}) != 3:
        raise ValueError("ULTRON_LAB_VARIANT_COLLISION")
    return items


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def assemble_clips(paths: list[Path], output: Path, *, pause_ms: int = 600) -> dict:
    """Produce ONE comparison WAV with audibly separated tracks; never overwrite."""
    if len(paths) != 3 or not 300 <= pause_ms <= 1500:
        raise ValueError("ULTRON_LAB_ASSEMBLY_INVALID")
    if output.exists():
        raise FileExistsError("ULTRON_LAB_OUTPUT_EXISTS")
    formats = []
    durations = []
    for path in paths:
        with wave.open(str(path), "rb") as src:
            if src.getcomptype() != "NONE" or src.getnframes() <= 0:
                raise ValueError("ULTRON_LAB_WAV_INVALID")
            formats.append((src.getnchannels(), src.getsampwidth(), src.getframerate()))
            durations.append(round(src.getnframes() / src.getframerate(), 3))
    if len(set(formats)) != 1 or formats[0][0] != 1 or formats[0][1] != 2:
        raise ValueError("ULTRON_LAB_WAV_FORMAT_MISMATCH")
    channels, sample_bytes, rate = formats[0]
    silence = b"\x00" * (int(rate * pause_ms / 1000) * channels * sample_bytes)
    fd, name = tempfile.mkstemp(prefix=".ultron_pron_", suffix=".wav", dir=output.parent)
    os.close(fd)
    draft = Path(name)
    try:
        with wave.open(str(draft), "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(sample_bytes)
            out.setframerate(rate)
            for index, path in enumerate(paths):
                if index:
                    out.writeframes(silence)
                with wave.open(str(path), "rb") as src:
                    while part := src.readframes(16384):
                        out.writeframes(part)
        os.replace(draft, output)
    finally:
        draft.unlink(missing_ok=True)
    return {
        "duration_segments_seconds": durations,
        "comparison_file": str(output),
        "comparison_sha256": _sha256(output),
        "comparison_bytes": output.stat().st_size,
        "pause_ms": pause_ms,
    }


def run_lab(text: str, manifest: str, out_dir: str) -> dict:
    choices = variants(text)
    root = Path(out_dir)
    if not root.is_absolute() or root.is_symlink():
        raise ChatterboxPreflightError("ULTRON_LAB_OUTPUT_INVALID")
    real = root.resolve()
    base = (LOG_ROOT / "pronunciation_f6_20261122").resolve()
    if real != base:
        raise ChatterboxPreflightError("ULTRON_LAB_OUTPUT_NOT_ALLOWED")
    root.mkdir(parents=True, exist_ok=True)
    tracks = [root / f"variant_{item['id']}.wav" for item in choices]
    combo = root / "comparison_ultron_3_variants.wav"
    receipt = root / "pronunciation_lab_receipt.json"
    if any(path.exists() for path in [*tracks, combo, receipt]):
        raise ChatterboxPreflightError("ULTRON_LAB_ALREADY_EXECUTED")
    config = TTSConfig(engine="chatterbox_ptbr", model=manifest)
    # Multiple tracks, one local model initialization. F5 handles game checks.
    rendered = ChatterboxBatchTTS().synthesize_many(
        [item["text"] for item in choices], tracks, config,
    )
    if game_active():
        raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
    comparison = assemble_clips(rendered, combo)
    evidence = {
        "status": "F6_REAL_LOCAL_PRONUNCIATION_TRIALS_AWAIT_HUMAN_REVIEW",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_text": text,
        "language": "pt",
        "model": "ResembleAI/Chatterbox-Multilingual-pt-br",
        "voice_reference": "synthetic_qwen_lab_only",
        "scope": "laboratory_only",
        "trial_variants": [
            {"id": item["id"], "text": item["text"],
             "wav": str(path), "sha256": _sha256(path)}
            for item, path in zip(choices, rendered)
        ],
        "comparison": comparison,
        "note": "ASR is auxiliary; human approval required for actual pronunciation.",
    }
    fd, temp = tempfile.mkstemp(prefix=".ultron_pron_receipt_", suffix=".json", dir=root)
    os.close(fd)
    staged = Path(temp)
    try:
        staged.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        os.replace(staged, receipt)
    finally:
        staged.unlink(missing_ok=True)
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ultron F6 PT-BR brand pronunciation LAB only")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    args = parser.parse_args(argv)
    result = run_lab(args.text, args.manifest, args.out_dir)
    print(json.dumps({"status": result["status"], **result["comparison"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
