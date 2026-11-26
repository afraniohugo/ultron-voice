"""Bounded native ASR transport for a local caller; never opens a microphone."""
from __future__ import annotations
import json
import os
import queue
import threading
import time
import sys
import wave
from pathlib import Path
from backend.engine.asr import create_engine

CHUNK_BYTES = 6400
MAX_BYTES = 120 * 32000

def pcm_blocks(source):
    """Read complete PCM frames, permitting short pipe reads."""
    pending = bytearray()
    total = 0
    while True:
        data = source.read(CHUNK_BYTES - len(pending))
        if not data:
            break
        total += len(data)
        if total > MAX_BYTES:
            raise ValueError("ASR_STREAM_LIMIT")
        pending.extend(data)
        if len(pending) == CHUNK_BYTES:
            yield bytes(pending)
            pending.clear()
    if len(pending) % 2:
        raise ValueError("ASR_TRUNCATED_PCM")
    if pending:
        yield bytes(pending)

class StreamIdleTimeout(TimeoutError):
    pass

class StreamCancelled(RuntimeError):
    pass

def timed_pcm_blocks(source, *, idle_timeout, cancelled=None):
    """Bound waiting on a CLI pipe; only the disposable worker owns this reader.

    A blocked OS read cannot be interrupted portably. The reader is daemonized;
    the CLI exits on failure. Do not use this adapter for a shared capture device.
    """
    inbox = queue.Queue(maxsize=2)
    stop = threading.Event()
    def offer(item):
        while not stop.is_set():
            try:
                inbox.put(item, timeout=0.1)
                return True
            except queue.Full:
                pass
        return False
    def read():
        try:
            for block in pcm_blocks(source):
                if not offer(("pcm", block)):
                    return
            offer(("eof", None))
        except Exception as exc:
            offer(("error", exc))
    thread = threading.Thread(target=read, name="asr-pipe-reader", daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + idle_timeout
        while True:
            if cancelled is not None and cancelled.is_set():
                raise StreamCancelled("ASR_CANCELLED")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise StreamIdleTimeout("ASR_IDLE_TIMEOUT")
            try:
                kind, value = inbox.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if kind == "eof":
                return
            if kind == "error":
                raise value
            yield value
            deadline = time.monotonic() + idle_timeout
    finally:
        stop.set()

def run(args, *, stdin=None, stdout=None, stderr=None, cancelled=None):
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    def emit(event):
        print(json.dumps(event, ensure_ascii=True, separators=(",",":")), file=stdout, flush=True)
    def check_cancelled():
        if cancelled is not None and cancelled.is_set():
            raise StreamCancelled("ASR_CANCELLED")
    try:
        check_cancelled()
        engine = create_engine("vosk")
        def guarded(blocks):
            for block in blocks:
                check_cancelled()
                yield block
        def consume(blocks):
            for event in engine.transcribe_stream(guarded(blocks), language=args.language):
                check_cancelled()
                emit(event)
        if args.pcm_stdin:
            consume(timed_pcm_blocks(stdin, idle_timeout=getattr(args, "idle_timeout", 10),
                                     cancelled=cancelled))
        else:
            raw = Path(args.wav)
            if str(raw).startswith(("\\\\", "//")):
                raise ValueError("ASR_LOCAL_WAV_REQUIRED")
            path = raw.resolve(strict=True)
            if str(path).startswith(("\\\\", "//")) or not path.is_file():
                raise ValueError("ASR_LOCAL_WAV_REQUIRED")
            with wave.open(str(path), "rb") as wav:
                if (wav.getframerate(),wav.getnchannels(),wav.getsampwidth(),wav.getcomptype()) != (16000,1,2,"NONE"):
                    raise ValueError("ASR_PCM16_MONO_16KHZ_REQUIRED")
                if wav.getnframes()*2 > MAX_BYTES:
                    raise ValueError("ASR_STREAM_LIMIT")
                def wav_blocks():
                    remaining = wav.getnframes() * 2
                    while remaining:
                        block = wav.readframes(min(CHUNK_BYTES, remaining)//2)
                        if not block or len(block) % 2 or len(block) > remaining:
                            raise ValueError("ASR_TRUNCATED_PCM")
                        remaining -= len(block)
                        yield block
                consume(wav_blocks())
        if cancelled is not None and cancelled.is_set():
            raise StreamCancelled("ASR_CANCELLED")
        emit({"type":"completed"})
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # No input path, audio or internal exception text in transport errors.
        code = ("ASR_IDLE_TIMEOUT" if isinstance(exc, StreamIdleTimeout)
                else "ASR_CANCELLED" if isinstance(exc, (StreamCancelled, KeyboardInterrupt))
                else type(exc).__name__)
        print(json.dumps({"type":"error","code":code}),file=stderr,flush=True)
        return 1


def run_worker(args):
    """Hard deadline only in the dedicated CLI process, never a shared host."""
    def expire():
        # Avoid buffered I/O and locks in a stuck native inference process.
        try:
            os.write(2, b'{"type":"error","code":"ASR_SESSION_TIMEOUT"}\n')
        finally:
            os._exit(124)
    timer = threading.Timer(args.session_timeout, expire)
    timer.daemon = True
    timer.start()
    try:
        # Raw stdin avoids a buffered-reader lock during interpreter shutdown.
        code = run(args, stdin=getattr(sys.stdin.buffer, "raw", sys.stdin.buffer))
        if code:
            sys.stdout.flush()
            sys.stderr.flush()
            # The dedicated worker may still own a blocked OS pipe read.
            os._exit(code)
        return code
    finally:
        timer.cancel()
