"""Local WAV session supervisor. No microphone, daemon or remote transport."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from .gameguard import game_active

MAX_LINE = 65536
MAX_EVENTS = 2048
_SINGLE_SESSION = threading.Lock()


class SessionError(RuntimeError):
    pass


def _command(path, language):
    return [sys.executable, "-m", "ultron_voice.cli", "asr-stream",
            "--wav", str(path), "--language", language,
            "--session-timeout", "180"]


def _local_path(path):
    raw = Path(path)
    if str(raw).startswith(("\\\\", "//")):
        raise SessionError("ASR_LOCAL_WAV_REQUIRED")
    path = raw.resolve(strict=True)
    if (str(path).startswith(("\\\\", "//")) or path.suffix.lower() != ".wav"
            or not path.is_file()):
        raise SessionError("ASR_LOCAL_WAV_REQUIRED")
    return path


def run_wav(path, *, language="pt", timeout=150, cancel=None, on_event=None):
    """Blocking supervisor; invoke from a UI worker thread.

    Partial/final segments are provisional until the returned completion.
    The callback must be nonblocking. Only our own Popen handle is stopped.
    """
    if language not in ("pt", "en") or not isinstance(timeout, (int, float)) or not 0 < timeout <= 180:
        raise ValueError("ASR_INVALID_SESSION")
    cancel = cancel if cancel is not None else threading.Event()
    if not _SINGLE_SESSION.acquire(blocking=False):
        raise SessionError("ASR_SESSION_BUSY")
    proc = None
    stopping = threading.Event()
    readers = []
    inbox = queue.Queue(maxsize=16)
    deadline = time.monotonic() + timeout
    def offer(item):
        while not stopping.is_set():
            try:
                inbox.put(item, timeout=0.05)
                return
            except queue.Full:
                continue

    def read_stdout():
        try:
            while not stopping.is_set():
                line = proc.stdout.readline(MAX_LINE + 1)
                if not line:
                    offer(("eof", None))
                    return
                if len(line) > MAX_LINE or not line.endswith(b"\n"):
                    raise ValueError("ASR_INVALID_LINE")
                offer(("line", line))
        except Exception:
            offer(("error", None))

    def drain_stderr():
        # Native decoder may write diagnostic logs; never retain or expose them.
        try:
            while not stopping.is_set() and proc.stderr.read(4096):
                pass
        except OSError:
            pass

    try:
        if cancel.is_set():
            raise SessionError("ASR_CANCELLED")
        path = _local_path(path)
        if game_active():
            raise SessionError("GAMEGUARD_ACTIVE")
        if cancel.is_set():
            raise SessionError("ASR_CANCELLED")
        if time.monotonic() >= deadline:
            raise SessionError("ASR_SESSION_TIMEOUT")
        env = {k: v for k, v in os.environ.items()
               if not any(marker in k.upper() for marker in
                          ("TOKEN", "API_KEY", "SECRET", "PASSWORD", "PROXY", "PYTHONPATH", "PYTHONHOME"))}
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
        proc = subprocess.Popen(_command(path, language), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, cwd=Path(__file__).resolve().parent.parent, bufsize=0,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for target in (read_stdout, drain_stderr):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            readers.append(thread)
        completed = False
        eof = False
        count = 0
        final = []
        while True:
            if cancel.is_set():
                raise SessionError("ASR_CANCELLED")
            if time.monotonic() >= deadline:
                raise SessionError("ASR_SESSION_TIMEOUT")
            if eof and proc.poll() is not None:
                break
            try:
                kind, value = inbox.get(timeout=0.05)
            except queue.Empty:
                continue
            if kind == "eof":
                eof = True
                continue
            if kind != "line" or completed:
                raise SessionError("ASR_INVALID_PROTOCOL")
            count += 1
            if count > MAX_EVENTS:
                raise SessionError("ASR_EVENT_LIMIT")
            try:
                event = json.loads(value)
            except (ValueError, UnicodeError) as exc:
                raise SessionError("ASR_INVALID_PROTOCOL") from exc
            if not isinstance(event, dict):
                raise SessionError("ASR_INVALID_PROTOCOL")
            kind = event.get("type")
            if kind == "completed" and set(event) == {"type"}:
                completed = True
                continue
            if (kind not in ("partial", "final") or set(event) != {"type", "text"}
                    or not isinstance(event.get("text"), str)
                    or len(event["text"]) > 4096):
                raise SessionError("ASR_INVALID_PROTOCOL")
            if kind == "final":
                final.append(event["text"])
            if on_event is not None:
                on_event(event)
        if cancel.is_set():
            raise SessionError("ASR_CANCELLED")
        if proc.returncode != 0 or not completed:
            raise SessionError("ASR_WORKER_FAILED")
        return {"status": "completed", "text": " ".join(final), "events": count}
    finally:
        stopping.set()
        try:
            if proc is not None:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)
                # On process exit, OS pipe handles close; never kill by name/PID lookup.
                for reader in readers:
                    reader.join(timeout=1)
                for pipe in (proc.stdout, proc.stderr):
                    if pipe is not None:
                        pipe.close()
        finally:
            _SINGLE_SESSION.release()
