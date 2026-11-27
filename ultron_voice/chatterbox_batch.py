"""F5: one-shot local batch of short PT-BR fragments with one model load.

No daemon, shared mutable model state, GPU or extra web service. Batch max 4.
Requires same F4 audited manifest, model/source hashes and synthetic reference.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from .chatterbox_ptbr import (
    ChatterboxPreflightError, ChatterboxPtBrTTS, inspect_manifest,
)
from .gameguard import game_active

MAX_ITEMS = 4
MAX_TOTAL_CHARS = 600


class ChatterboxBatchTTS(ChatterboxPtBrTTS):
    def synthesize_many(self, texts: list[str], outputs: list[Path], config) -> list[Path]:
        if not isinstance(texts, list) or not isinstance(outputs, list):
            raise ValueError("CHATTERBOX_BATCH_INVALID")
        if not 2 <= len(texts) <= MAX_ITEMS or len(texts) != len(outputs):
            raise ValueError("CHATTERBOX_BATCH_SIZE_INVALID")
        if (any(not isinstance(t, str) or not t.strip() or len(t) > 280 for t in texts)
                or sum(len(t) for t in texts) > MAX_TOTAL_CHARS):
            raise ValueError("CHATTERBOX_BATCH_TEXT_INVALID")
        paths = [Path(path) for path in outputs]
        if len(set(paths)) != len(paths) or any(path.suffix.lower() != ".wav" for path in paths):
            raise ValueError("CHATTERBOX_BATCH_OUTPUT_INVALID")
        if game_active():
            raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
        settings = inspect_manifest(config.model)
        worker = Path(__file__).with_name("chatterbox_batch_worker.py")
        if not worker.is_file():
            raise ChatterboxPreflightError("CHATTERBOX_BATCH_WORKER_MISSING")
        parents = {str(p.parent.resolve()) for p in paths}
        if len(parents) != 1:
            raise ValueError("CHATTERBOX_BATCH_ONE_OUTPUT_DIRECTORY")
        destination_parent = paths[0].parent
        destination_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="uv_chatterbox_batch_", dir=destination_parent) as tmp:
            drafts = [Path(tmp) / ("track_%03d.wav" % i) for i in range(len(texts))]
            request_path = Path(tmp) / "request.json"
            request_path.write_text(
                json.dumps(dict(settings, items=[{"text": t, "output": str(d)}
                                                for t, d in zip(texts, drafts)]),
                           ensure_ascii=False), encoding="utf-8",
            )
            allow = {
                "SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE",
                "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "COMSPEC",
            }
            env = {k: v for k, v in os.environ.items() if k.upper() in allow}
            env.update({
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                "CUDA_VISIBLE_DEVICES": "", "PYTHONNOUSERSITE": "1",
                "OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4",
            })
            process = subprocess.Popen(
                [settings["runtime_python"], "-I", str(worker), str(request_path)],
                cwd=tmp, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            started = time.monotonic()
            try:
                while True:
                    try:
                        process.communicate(timeout=3)
                        break
                    except subprocess.TimeoutExpired:
                        if game_active():
                            process.kill()
                            process.communicate()
                            raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
                        if time.monotonic() - started > 480:
                            process.kill()
                            process.communicate()
                            raise ChatterboxPreflightError("CHATTERBOX_BATCH_TIMEOUT")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            if process.returncode != 0:
                raise ChatterboxPreflightError("CHATTERBOX_BATCH_WORKER_FAILED")
            if any(not f.is_file() or f.stat().st_size < 80 for f in drafts):
                raise ChatterboxPreflightError("CHATTERBOX_BATCH_MISSING_AUDIO")
            expected_format = None
            for draft in drafts:
                with wave.open(str(draft), "rb") as wav:
                    fmt = (wav.getnchannels(), wav.getsampwidth(),
                           wav.getframerate(), wav.getcomptype())
                    if wav.getnframes() <= 0 or fmt[-1] != "NONE":
                        raise ChatterboxPreflightError("CHATTERBOX_BATCH_INVALID_WAV")
                    if expected_format is None:
                        expected_format = fmt
                    elif expected_format != fmt:
                        raise ChatterboxPreflightError("CHATTERBOX_BATCH_MISMATCH_FORMAT")
            if game_active():
                raise ChatterboxPreflightError("GAMEGUARD_ACTIVE")
            for draft, path in zip(drafts, paths):
                os.replace(draft, path)
        return paths
