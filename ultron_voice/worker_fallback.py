"""Fail-closed device retry policy for isolated local TTS workers."""
from __future__ import annotations

from collections.abc import Callable


class WorkerGameGuardActive(RuntimeError):
    """GameGuard became active between the adapter preflight and worker launch."""


class WorkerFallbackFailure(RuntimeError):
    """The configured worker attempts failed without leaking runtime details."""


def run_with_cpu_fallback(
    primary_device: str,
    attempt: Callable[[str], int],
    game_active: Callable[[], bool],
) -> str:
    """Retry once on CPU only after an XPU worker exception (exit 5).

    Validation errors, invalid audio, timeouts, and GameGuard stops never retry.
    The caller keeps its inter-process model lock for the entire sequence.
    """
    if primary_device == "cpu":
        devices = ("cpu",)
    elif primary_device in ("xpu", "auto"):
        devices = ("xpu", "cpu")
    else:
        raise ValueError("NEURAL_DEVICE_INVALID")

    for device in devices:
        if game_active():
            raise WorkerGameGuardActive("GAMEGUARD_ACTIVE")
        exit_code = attempt(device)
        if exit_code == 0:
            return device
        if device == "xpu" and exit_code == 5:
            if game_active():
                raise WorkerGameGuardActive("GAMEGUARD_ACTIVE")
            continue
        raise WorkerFallbackFailure("LOCAL_TTS_WORKER_FAILED")
    raise WorkerFallbackFailure("LOCAL_TTS_WORKER_FAILED")
