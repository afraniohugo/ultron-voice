"""Process-local half-duplex admission for future audio device adapters.

No microphone or playback is opened here. Callers must hold the lease for
the entire actual device lifetime, including teardown.
"""
from contextlib import contextmanager
import threading
import time
from .gameguard import game_active


class AudioTurnError(RuntimeError):
    pass


class AudioTurns:
    def __init__(self, *, tail_seconds=0.35):
        if not 0 <= tail_seconds <= 2:
            raise ValueError("AUDIO_INVALID_TAIL")
        self._lock = threading.Lock()
        self._active = None
        self._tail_until = 0.0
        self._tail = tail_seconds

    @property
    def state(self):
        with self._lock:
            if self._active:
                return self._active
            if time.monotonic() < self._tail_until:
                return "echo_tail"
            return "idle"

    @contextmanager
    def lease(self, kind, *, consent=False):
        if kind not in ("capture", "playback"):
            raise ValueError("AUDIO_INVALID_TURN")
        if consent is not True:
            raise AudioTurnError("AUDIO_EXPLICIT_CONSENT_REQUIRED")
        if game_active():
            raise AudioTurnError("GAMEGUARD_ACTIVE")
        with self._lock:
            if self._active is not None:
                raise AudioTurnError("AUDIO_TURN_BUSY")
            if kind == "capture" and time.monotonic() < self._tail_until:
                raise AudioTurnError("AUDIO_ECHO_TAIL")
            self._active = kind
        try:
            if game_active():
                raise AudioTurnError("GAMEGUARD_ACTIVE")
            yield
        finally:
            with self._lock:
                if kind == "playback":
                    self._tail_until = time.monotonic() + self._tail
                self._active = None


# Single admission controller per application process, not a host-wide lock.
audio_turns = AudioTurns()
