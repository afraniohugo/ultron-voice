"""Bounded native ASR transport for a local caller; never opens a microphone."""
from __future__ import annotations
import json
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

def run(args, *, stdin=None, stdout=None, stderr=None):
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    def emit(event):
        print(json.dumps(event, ensure_ascii=True, separators=(",",":")), file=stdout, flush=True)
    try:
        engine = create_engine("vosk")
        def consume(blocks):
            for event in engine.transcribe_stream(blocks, language=args.language):
                emit(event)
        if args.pcm_stdin:
            consume(pcm_blocks(stdin))
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
        emit({"type":"completed"})
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # No input path, audio or internal exception text in transport errors.
        print(json.dumps({"type":"error","code":type(exc).__name__}),file=stderr,flush=True)
        return 1
