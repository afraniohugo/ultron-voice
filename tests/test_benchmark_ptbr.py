"""Tests for the Chatterbox PT-BR single vs batch benchmark harness.

All tests are unit/integration level: no neural weights are loaded and no
audio is issued.  A deterministic fake engine writes synthetic WAV files, so
the suite is fast, reproducible and never touches the MIT weights.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultron_voice.chatterbox_ptbr import ChatterboxPtBrTTS  # noqa: E402
from ultron_voice.benchmark_ptbr import (  # noqa: E402
    BenchmarkConfig,
    BenchmarkResult,
    InterProcessLock,
    LockTimeout,
    chunk_texts,
    run_benchmark,
    write_run_artifacts,
)
from ultron_voice.tts import TTSConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic fake engine (no model, no weights)
# ---------------------------------------------------------------------------


class FakeEngine(ChatterboxPtBrTTS):
    """Writes a synthetic 0.4s WAV per call; timings are measured only."""

    def synthesize(self, text: str, out_path, config) -> Path:  # type: ignore[override]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x00\xff" * 4800)  # 0.4s @24kHz
        return out_path

    def synthesize_many(self, texts, outputs, config):  # type: ignore[override]
        assert isinstance(config, TTSConfig)
        for text, out in zip(texts, outputs):
            self.synthesize(text, out, config)
        return [Path(out) for out in outputs]


@pytest.fixture(autouse=True)
def isolate_fake_engine_manifest(monkeypatch):
    # This suite exercises FakeEngine only; real weight integrity is tested
    # separately in test_chatterbox_ptbr_f4.py. Never read production assets here.
    monkeypatch.setattr(
        "ultron_voice.benchmark_ptbr.inspect_manifest",
        lambda manifest: {"status": "TEST_FAKE_ENGINE", "manifest": manifest},
    )


@pytest.fixture()
def config(tmp_path):
    return BenchmarkConfig(
        num_texts=2,
        run_root=tmp_path / "benchmarks",
        lock_root=tmp_path / "lock",
    )


# ---------------------------------------------------------------------------
# InterProcessLock
# ---------------------------------------------------------------------------


def test_lock_acquire_release_and_remove(tmp_path):
    lock = InterProcessLock(tmp_path / "benchmark.pid")
    lock.acquire()
    assert lock.path.exists()
    assert lock.owner == os.getpid()
    lock.release()
    assert not lock.path.exists()


def test_lock_exclusivity(tmp_path):
    lock = InterProcessLock(tmp_path / "benchmark.pid")
    lock.acquire()
    contender = InterProcessLock(tmp_path / "benchmark.pid")
    timed_out = False
    try:
        contender.acquire(timeout=1.0)
    except LockTimeout:
        timed_out = True
    finally:
        lock.release()
    assert timed_out


def test_lock_stale_owner_is_not_stolen(tmp_path):
    path = tmp_path / "benchmark.pid"
    path.write_text("999999\n", encoding="ascii")
    with pytest.raises(LockTimeout):
        InterProcessLock(path).acquire(timeout=0)
    assert path.read_text(encoding="ascii").strip() == "999999"

# ---------------------------------------------------------------------------
# chunk_texts
# ---------------------------------------------------------------------------


def test_chunk_texts_limits():
    texts = ["a" * 200 for _ in range(6)]
    chunks = chunk_texts(texts)
    assert [len(c) for c in chunks] == [3, 3]
    total = sum(len(t) for c in chunks for t in c)
    assert total == 6 * 200


# ---------------------------------------------------------------------------
# Benchmark harness with a fake engine
# ---------------------------------------------------------------------------


def _run_fake(config: BenchmarkConfig):
    """Skip instead of failing if GameGuard flips during the canary.

    The production gate still fails closed; only the lab suite defers.
    """
    try:
        return run_benchmark(config, engine_factory=FakeEngine())
    except Exception as exc:
        if "GAMEGUARD_ACTIVE" in str(exc):
            pytest.skip("GameGuard became active during benchmark")
        raise


def _run(config: BenchmarkConfig):
    return _run_fake(config)


def test_benchmark_runs_single_and_batch_with_same_texts(config):
    result = _run(config)
    assert len(result.single) == 2
    assert len(result.batch) == 1
    assert result.batch[0].items == 2
    assert result.speedups_claimed is False
    assert "speedup" not in result.note.lower().replace("no speedup", "")
    assert result.note.startswith("raw timings only")


def test_benchmark_result_records_checksums(config, tmp_path):
    result = _run_fake(config)
    for m in result.single:
        assert m.wav.exists()
        assert len(m.sha256) == 64
        assert m.bytes > 0
        assert m.duration_s > 0
    assert result.run_root.exists()


def test_benchmark_receipt_has_no_speedup_claim(config, tmp_path):
    result = _run_fake(config)
    receipt = json.loads(
        (result.run_root / "benchmark_receipt.json").read_text(encoding="utf-8")
    )
    assert receipt["speedups_claimed"] is False
    assert receipt["baseline_invalid"] == (
        r"E:\IA LOCAL\logs\ultron_voice\benchmark_f6_20261123\invalidated_comparison.json"
    )


def test_rerun_creates_unique_run_tree(config, tmp_path):
    first = _run_fake(config)
    second = _run_fake(config)
    assert first.run_root != second.run_root
    assert (first.run_root / "benchmark_receipt.json").is_file()
    assert (second.run_root / "benchmark_receipt.json").is_file()
    assert len(list(first.run_root.rglob("*.wav"))) >= 2
    assert len(list(second.run_root.rglob("*.wav"))) >= 2


def test_gameguard_abort_does_not_writedir(config, monkeypatch):
    monkeypatch.setattr("ultron_voice.benchmark_ptbr.game_active", lambda: True)
    with pytest.raises(Exception):
        run_benchmark(
            config, engine_factory=FakeEngine()
        )
    assert not (config.run_root / "benchmark_receipt.json").exists()


# ---------------------------------------------------------------------------
# Persistence: unique paths, no overwrites
# ---------------------------------------------------------------------------


def test_write_run_artifacts_is_idempotent_per_run(tmp_path):
    config = BenchmarkConfig(
        num_texts=1,
        run_root=tmp_path / "benchmarks",
        lock_root=tmp_path / "lock",
    )
    first = _run_fake(config)
    first_root = write_run_artifacts(first)
    assert (first_root / "benchmark_receipt.json").is_file()
    # A second run with the same texts gets a NEW run directory.
    second = _run_fake(config)
    second_root = write_run_artifacts(second)
    assert second_root != first_root
    assert (
        second_root / "benchmark_receipt.json"
    ).read_text(encoding="utf-8") != first_root.joinpath("benchmark_receipt.json").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# CLI self-test: lock exclusivity across real OS processes
# ---------------------------------------------------------------------------


def test_self_test_lock_exclusivity(tmp_path):
    lock_path = tmp_path / "benchmark.pid"
    repo_root = Path(__file__).resolve().parents[1]
    script = (
        "import os, sys, time\n"
        "repo = os.environ.get('ULTRON_VOICE_REPO')\n"
        "if repo:\n"
        "    if repo not in sys.path:\n"
        "        sys.path.insert(0, repo)\n"
        "from ultron_voice.benchmark_ptbr import InterProcessLock\n"
        "p = InterProcessLock(__import__('pathlib').Path(sys.argv[1]))\n"
        "p.acquire()\n"
        "time.sleep(0.8)\n"
        "p.release()\n"
        "print('HOLDER_DONE')\n"
    )
    env = dict(os.environ)
    env["ULTRON_VOICE_REPO"] = str(repo_root)
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(lock_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10.0
        lock_seen = False
        while time.monotonic() < deadline:
            if lock_path.exists():
                lock_seen = True
                break
            time.sleep(0.05)
        assert lock_seen, "holder did not create the lock file"
        contender = InterProcessLock(lock_path)
        timed_out = False
        try:
            # The holder sleeps 0.8s; a shorter timeout guarantees the
            # contender sees a live owner and must be rejected.
            contender.acquire(timeout=0.2)
        except LockTimeout:
            timed_out = True
        finally:
            contender.release()
        assert timed_out, "contender acquired the lock while the holder was active"
        proc.wait(timeout=10)
        assert proc.returncode == 0, proc.stderr.read().decode("utf-8", "replace")
        assert b"HOLDER_DONE" in proc.stdout.read()
        assert not lock_path.exists(), "holder did not release the lock"
    finally:
        if lock_path.exists():
            lock_path.unlink(missing_ok=True)
