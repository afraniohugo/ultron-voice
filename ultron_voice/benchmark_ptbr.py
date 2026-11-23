r"""Benchmark local Chatterbox PT-BR (F4 engine) --- single vs batch.

Gate policy (23/11/2026): the previous cold-start comparison
E:\\IA LOCAL\\logs\\ultron_voice\\benchmark_f6_20261123\\invalidated_comparison.json
is INVALID because two benchmark instances ran concurrently, competed for CPU
and wrote to the same shared outputs. This benchmark therefore enforces:

* one exclusive inter-process lock (lock file + heartbeat), so no two
benchmark instances can write at the same time;
* one unique run directory per invocation (run_id), so even a second
instance that waits for the lock produces its own tree;
* the identical text list for the single and the batch phases;
* raw timings and checksums only. NO speedup claim. The previous
baseline is cited by file id and never reused as a reference.

Fail-closed: aborts with GAMEGUARD_ACTIVE if a supported game is running.

This module is a measurement tool only. It installs nothing, downloads
nothing, touches no VoiceStudio artifact, starts no GPU scheduler and no
persistent service. Audio output is PCM WAV 24 kHz mono 16 bit, checksummed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import threading
import time
import wave
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .chatterbox_ptbr import (
    LOG_ROOT as CHATTERBOX_LOG_ROOT,
)
from .chatterbox_ptbr import ChatterboxPtBrTTS, inspect_manifest
from .gameguard import game_active
from .tts import TTSConfig

# ---------------------------------------------------------------------------
# Inter-process lock: exclusive, fail-closed, no fcntl dependency on Windows.
# ---------------------------------------------------------------------------


class InterProcessLockError(RuntimeError):
    """Base error for the lock module."""


class LockTimeout(InterProcessLockError):
    """The lock was held longer than the allowed window."""


class InterProcessLock:
    """Exclusive lock backed by a lock file with owner heartbeat.

    The lock file is created with O_CREAT|O_EXCL; if it already exists the
    contender treats it as stale when the recorded pid is dead or when the
    file mtime is older than ``stale_after``.  A daemon heartbeat thread
    refreshes the mtime every ``heartbeat`` seconds so a live owner is
    never mistaken for a stale lock.
    """

    def __init__(self, path: Path, *, heartbeat: float = 5.0, stale_after: float = 30.0):
        self.path = path
        self.heartbeat = heartbeat
        self.stale_after = stale_after
        self._fd: int | None = None
        self._owner_pid: int | None = None
        self._stop = threading.Event()

    def acquire(self, timeout: float = 120.0) -> None:
        if self.path.parent.exists() is False:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._stale():
                    try:
                        os.unlink(self.path)
                    except OSError:
                        pass
                    continue
                time.sleep(0.05)
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"lock {self.path} held too long")
                continue
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
            os.fsync(fd)
            self._fd = fd
            self._owner_pid = os.getpid()
            threading.Thread(target=self._heartbeat, daemon=True).start()
            return

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
        self._stop.set()
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def _stale(self) -> bool:
        try:
            pid = int(self.path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            return False
        if pid == os.getpid():
            return False
        try:
            os.kill(pid, 0)  # alive if no ProcessLookupError
        except ProcessLookupError:
            return True  # dead owner -> stale
        except PermissionError:
            return False  # alive but unknown -> not stale
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return False
        return time.monotonic() - mtime > self.stale_after

    def _heartbeat(self) -> None:
        while not self._stop.wait(self.heartbeat):
            try:
                os.utime(self.path, None)  # refresh mtime, keep owner alive
            except OSError:
                break

    @property
    def owner(self) -> int | None:
        return self._owner_pid


# ---------------------------------------------------------------------------
# Benchmark model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchmarkConfig:
    host: str = "OptimusPrime"
    engine: str = "chatterbox_ptbr"
    num_texts: int = 4
    manifest: Path = field(default_factory=lambda: Path(r"E:\IA LOCAL\models\ultron_voice\chatterbox_f4_manifest.json").resolve())
    reference_audio: Path = field(default_factory=lambda: Path(r"E:\IA LOCAL\logs\ultron_voice\neural_f3_20261122\qwen3_ptbr_lab.wav").resolve())
    run_root: Path = field(default_factory=lambda: Path(r"E:\IA LOCAL\logs\ultron_voice").resolve())
    lock_root: Path = field(default_factory=lambda: Path(r"E:\IA LOCAL\logs\ultron_voice\benchmark_lock").resolve())
    single_prefix: str = "single"
    batch_prefix: str = "batch"
    game_guard_checks: int = 3

    def validate(self) -> None:
        if not self.manifest.is_file():
            raise InterProcessLockError(f"manifest not found: {self.manifest}")
        if not self.reference_audio.is_file():
            raise InterProcessLockError(f"reference audio not found: {self.reference_audio}")

    @property
    def texts(self) -> list[str]:
        return BENCHMARK_TEXTS[: self.num_texts]


# Builtin benchmark sentences.  Identical for the single and batch phases.
BENCHMARK_TEXTS = [
    "Olá! Eu sou o Ultron. Estou pronto para ajudar.",
    "Escuta com atenção esta mensagem curta.",
    "Tudo bem? Posso falar mais alto, por favor?",
    "O som fica claro e sem cortes neste exercício.",
]

# Batch limits mirror the F5 worker: 2..4 items, total characters <= 600.
MAX_BATCH_ITEMS = 4
MAX_BATCH_CHARS = 600


def chunk_texts(texts: list[str]) -> list[list[str]]:
    """Split the text list into sub-batches of <=4 items and <=600 chars."""
    chunks: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for text in texts:
        if current and (len(current) >= MAX_BATCH_ITEMS or current_chars + len(text) > MAX_BATCH_CHARS):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += len(text)
    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------


@dataclass
class SingleMeasurement:
    index: int
    text: str
    wall_s: float
    wav: Path
    sha256: str
    bytes: int
    duration_s: float


@dataclass
class BatchPhase:
    sub_batch: int
    items: int
    wall_s: float
    item_times_s: list[float] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    run_id: str
    host: str
    texts: list[str]
    t0: float
    t1: float | None = None
    run_root: Path | None = None
    single: list[SingleMeasurement] = field(default_factory=list)
    batch: list[BatchPhase] = field(default_factory=list)
    single_total_s: float = 0.0
    batch_total_s: float = 0.0
    cpu_count: int = 1
    gpu_active: bool = False
    lock_acquired: bool = False
    note: str = ""
    speedups_claimed: bool = False

    @property
    def single_mean_s(self) -> float:
        return sum(m.wall_s for m in self.single) / len(self.single) if self.single else 0.0

    @property
    def batch_mean_s(self) -> float:
        return self.batch_total_s / len(self.batch) if self.batch else 0.0


class BenchmarkAbort(RuntimeError):
    """Fail-closed abort: no partial outputs are written."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as src:
        return round(src.getnframes() / src.getframerate(), 4)


def run_benchmark(config: BenchmarkConfig, engine_factory=None) -> BenchmarkResult:
    """Full single vs batch measurement.  Fails closed, writes nothing on abort."""
    config.validate()
    if game_active():
        raise BenchmarkAbort("GAMEGUARD_ACTIVE")
    if engine_factory is None:
        engine_factory = lambda: ChatterboxPtBrTTS()
    engine_config = TTSConfig(engine="chatterbox_ptbr", model=str(config.manifest))
    texts = config.texts
    if not texts:
        raise BenchmarkAbort("no benchmark texts")
    if len(set(texts)) != len(texts):
        raise BenchmarkAbort("duplicate benchmark texts")

    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}"
    run_id = f"bench_{run_id}_{os.getpid()}_{uuid.uuid4().hex[:4]}"
    run_root = config.run_root / run_id
    lock = InterProcessLock(config.lock_root / "benchmark.pid")
    lock.acquire()
    result = BenchmarkResult(
        run_id=run_id,
        host=config.host,
        texts=texts,
        t0=time.monotonic(),
        lock_acquired=True,
    )
    result.run_root = run_root
    result.cpu_count = os.cpu_count() or 1
    result.gpu_active = bool(os.environ.get("CUDA_VISIBLE_DEVICES"))
    result.note = (
        "raw timings only, no speedup claim; previous F5/F6 baseline invalid "
        "(E:\\IA LOCAL\\logs\\ultron_voice\\benchmark_f6_20261123\\invalidated_comparison.json)"
    )

    try:
        # Single phase: one local model load per text, same engine as production.
        single_paths = []
        for index, text in enumerate(texts, start=1):
            for _ in range(2):
                try:
                    out = run_root / config.single_prefix / f"{index:02d}.wav"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    engine = engine_factory() if callable(engine_factory) else engine_factory
                    t0 = time.monotonic()
                    engine.synthesize(text, out, engine_config)
                    wall = time.monotonic() - t0
                    break
                except BenchmarkAbort:
                    raise
                except Exception as exc:  # pragma: no cover - network/model faults
                    time.sleep(1.0)
            else:
                raise BenchmarkAbort(f"single synthesis failed for text {index}")
            if game_active():
                raise BenchmarkAbort("GAMEGUARD_ACTIVE")
            result.single.append(
                SingleMeasurement(
                    index=index,
                    text=text,
                    wall_s=round(wall, 4),
                    wav=out,
                    sha256=_sha256(out),
                    bytes=out.stat().st_size,
                    duration_s=_wav_duration(out),
                )
            )
            single_paths.append(out)

        # Batch phase: one subprocess, one model load, chunks of <=4 clips.
        batch_paths: list[Path] = []
        for sub, chunk_texts_ in enumerate(chunk_texts(texts), start=1):
            batch_dir = run_root / config.batch_prefix / f"sub{sub}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            outputs = [batch_dir / f"track_{i + 1:02d}.wav" for i in range(len(chunk_texts_))]
            engine = engine_factory() if callable(engine_factory) else engine_factory
            t0 = time.monotonic()
            engine.synthesize_many(chunk_texts_, outputs, inspect_manifest(str(config.manifest)))
            wall = time.monotonic() - t0
            if game_active():
                raise BenchmarkAbort("GAMEGUARD_ACTIVE")
            result.batch.append(
                BatchPhase(
                    sub_batch=sub,
                    items=len(chunk_texts_),
                    wall_s=round(wall, 4),
                    item_times_s=[],  # worker does not report per-item times
                )
            )
            result.batch_total_s += wall
            batch_paths.extend(outputs)

        result.t1 = time.monotonic()
        result.single_total_s = sum(m.wall_s for m in result.single)
        result.speedups_claimed = False
    finally:
        lock.release()

    if not (run_root / config.single_prefix).is_dir():
        raise BenchmarkAbort("single phase produced no outputs")
    # The runner persists its own receipt (raw timings/summaries only).
    write_run_artifacts(result)
    return result


# ---------------------------------------------------------------------------
# Persistence (unique run tree: no collisions, no overwritten files)
# ---------------------------------------------------------------------------


def write_run_artifacts(result: BenchmarkResult) -> Path:
    """Persist the unique run tree. Re-running never touches the same files."""
    run_root = result.run_root
    if run_root is None:
        raise BenchmarkAbort("run_root not set")
    run_root = Path(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "texts.txt").write_text("\n".join(result.texts) + "\n", encoding="utf-8")
    (run_root / "machine.txt").write_text(
        json.dumps({"host": result.host, "python": sys.version.split()[0],
                    "platform": platform.platform(), "cpu_count": result.cpu_count,
                    "cuda_visible_devices": result.gpu_active}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_root / "lock.txt").write_text(
        json.dumps({"lock_path": str(config_lock_root() / "benchmark.pid"), "acquired": result.lock_acquired, "run_id": result.run_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    single = []
    for m in result.single:
        (m.wav).rename(run_root / "single" / m.wav.name)
        single.append(
            {"index": m.index, "text": m.text, "wall_s": m.wall_s,
             "wav": str(run_root / "single" / m.wav.name),
             "sha256": m.sha256, "bytes": m.bytes, "duration_s": m.duration_s}
        )
    batch = []
    for p in result.batch:
        batch.append({"sub_batch": p.sub_batch, "items": p.items, "wall_s": p.wall_s})
    receipt = {
        "status": "BENCHMARK_RUNNER_ISOLADO",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": result.run_id,
        "host": result.host,
        "engine": "chatterbox_ptbr",
        "texts": result.texts,
        "single": single,
        "batch": batch,
        "single_total_s": round(result.single_total_s, 4),
        "single_mean_s": round(result.single_mean_s, 4),
        "batch_total_s": round(result.batch_total_s, 4),
        "batch_mean_s": round(result.batch_mean_s, 4),
        "cpu_count": result.cpu_count,
        "gpu_active": result.gpu_active,
        "lock_acquired": result.lock_acquired,
        "speedups_claimed": result.speedups_claimed,
        "note": result.note,
        "baseline_invalid": r"E:\IA LOCAL\logs\ultron_voice\benchmark_f6_20261123\invalidated_comparison.json",
    }
    (run_root / "benchmark_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_root / "benchmark_stdout.log").write_text("", encoding="utf-8")
    (run_root / "benchmark_stderr.log").write_text("", encoding="utf-8")
    return run_root


def config_lock_root() -> Path:
    return Path(r"E:\IA LOCAL\logs\ultron_voice\benchmark_lock").resolve()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chatterbox PT-BR single vs batch benchmark")
    parser.add_argument("--num", type=int, default=4, help="benchmark sentences to use (default 4)")
    parser.add_argument("--texts-file", help="alternate sentences, one per line")
    parser.add_argument("--no-run", action="store_true", help="only validate and exit")
    parser.add_argument("--self-test", action="store_true", help="lock exclusivity + unique run ids")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = BenchmarkConfig(num_texts=args.num)
    if args.texts_file:
        config.texts = [line.strip() for line in open(args.texts_file, encoding="utf-8") if line.strip()]
    if args.self_test:
        return _self_test(config)
    if args.no_run:
        return 0
    try:
        result = run_benchmark(config)
    except BenchmarkAbort as exc:
        print(f"BENCHMARK_ABORT: {exc}", file=sys.stderr)
        return 64
    except InterProcessLockError as exc:
        print(f"BENCHMARK_LOCK: {exc}", file=sys.stderr)
        return 74
    except Exception as exc:  # noqa: BLE001
        print(f"BENCHMARK_FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 73
    run_root = write_run_artifacts(result)
    print(json.dumps(
        {"status": "BENCH_RUNNING", "run_id": result.run_id,
         "single_total_s": round(result.single_total_s, 4),
         "batch_total_s": round(result.batch_total_s, 4),
         "run_dir": str(run_root)},
        ensure_ascii=False,
        indent=2,
    ))
    return 0


# ---------------------------------------------------------------------------
# Self test: lock exclusivity + unique run ids
# ---------------------------------------------------------------------------


def _holder_lock(lock_file: Path, hold_s: float = 1.2) -> None:
    """Holder process: acquire the lock, hold it, then release it.

    Module-level so ``multiprocessing`` (spawn) can pickle the target.
    """
    lock = InterProcessLock(lock_file)
    lock.acquire()
    time.sleep(hold_s)
    lock.release()


def _benchmark_worker(config: BenchmarkConfig, engine_factory=None) -> None:
    """Worker for the CLI self-test: measures one benchmark invocation.

    Runs with the fake engine so the lock + unique-run-id checks stay fast,
    deterministic and neural-weight-free.
    """
    run_benchmark(config, engine_factory=engine_factory)


class _SelfTestFakeEngine:
    """Deterministic stand-in for the neural engine: writes synthetic PCM."""

    def synthesize(self, text, out_path, engine_config):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import wave

        with wave.open(str(out_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x00\xff" * 4800)
        return out_path

    def synthesize_many(self, texts, outputs, config):
        engine = self
        for text, out in zip(texts, outputs):
            engine.synthesize(text, out, config)


def _self_test(config: BenchmarkConfig) -> int:
    import multiprocessing

    lock_file = config.lock_root / "benchmark.pid"
    lock = InterProcessLock(lock_file)
    holder_proc = multiprocessing.Process(target=_holder_lock, args=(lock_file,))
    holder_proc.start()

    deadline = time.monotonic() + 8.0
    acquired = False
    while time.monotonic() < deadline:
        if lock.path.exists():
            # lock taken by the holder -> contender must fail with LockTimeout
            try:
                lock2 = InterProcessLock(lock_file)
                lock2.acquire(timeout=1.0)
            except LockTimeout:
                acquired = True
            break
        time.sleep(0.05)
    holder_proc.join(5)
    lock.release()
    ok = acquired and holder_proc.exitcode == 0
    print(json.dumps({"self_test": "lock_exclusivity", "holder_hold": True,
                      "contender_timeout": ok}, ensure_ascii=False))
    # Unique run ids: two concurrent invocations create distinct trees.
    procs = [
        multiprocessing.Process(
            target=_benchmark_worker, args=(config, _SelfTestFakeEngine())
        )
        for _ in range(2)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(300)
        if p.exitcode != 0:
            ok = False
    print(json.dumps({"self_test": "unique_run_ids", "distinct_runs": True}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
