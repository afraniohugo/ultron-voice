import pytest

from ultron_voice.worker_fallback import (
    WorkerFallbackFailure,
    run_with_cpu_fallback,
)


def test_xpu_exception_retries_cpu_once():
    attempts = []

    def run(device):
        attempts.append(device)
        return 5 if device == "xpu" else 0

    assert run_with_cpu_fallback("xpu", run, lambda: False) == "cpu"
    assert attempts == ["xpu", "cpu"]


def test_cpu_only_never_retries():
    attempts = []
    with pytest.raises(WorkerFallbackFailure):
        run_with_cpu_fallback("cpu", lambda device: attempts.append(device) or 5, lambda: False)
    assert attempts == ["cpu"]


def test_invalid_audio_or_request_does_not_fallback():
    attempts = []
    with pytest.raises(WorkerFallbackFailure):
        run_with_cpu_fallback("xpu", lambda device: attempts.append(device) or 4, lambda: False)
    assert attempts == ["xpu"]


def test_non_xpu_worker_exception_does_not_fallback():
    attempts = []
    with pytest.raises(WorkerFallbackFailure):
        run_with_cpu_fallback(
            "xpu", lambda device: attempts.append(device) or 6, lambda: False
        )
    assert attempts == ["xpu"]


def test_gameguard_blocks_retry_after_xpu_failure():
    attempts = []
    game = {"active": False}

    def run(device):
        attempts.append(device)
        game["active"] = True
        return 5

    with pytest.raises(RuntimeError, match="GAMEGUARD_ACTIVE"):
        run_with_cpu_fallback("xpu", run, lambda: game["active"])
    assert attempts == ["xpu"]


def test_timeout_exception_is_not_retried():
    attempts = []

    def run(device):
        attempts.append(device)
        raise TimeoutError("worker timeout")

    with pytest.raises(TimeoutError):
        run_with_cpu_fallback("xpu", run, lambda: False)
    assert attempts == ["xpu"]
