"""Real child-process tests with inert fixture decoders."""
import sys
import threading
import time
from pathlib import Path
import pytest
from ultron_voice import asr_supervisor as supervisor

@pytest.fixture
def wav(tmp_path, monkeypatch):
    path = tmp_path / "fixture.wav"
    path.touch()
    monkeypatch.setattr(supervisor, "game_active", lambda: False)
    return path

def worker(monkeypatch, code):
    monkeypatch.setattr(supervisor, "_command",
                        lambda path, language: [sys.executable, "-u", "-c", code])

def test_terminal_requires_exit_zero(wav, monkeypatch):
    worker(monkeypatch, 'print(\'{"type":"final","text":"ola"}\');print(\'{"type":"completed"}\')')
    events=[]
    assert supervisor.run_wav(wav, timeout=5,on_event=events.append) == {
        "status":"completed","text":"ola","events":2}
    assert events == [{"type":"final","text":"ola"}]
    worker(monkeypatch, 'print(\'{"type":"completed"}\');raise SystemExit(2)')
    with pytest.raises(supervisor.SessionError,match="WORKER_FAILED"):
        supervisor.run_wav(wav,timeout=5)

@pytest.mark.parametrize("code", [
    'print("not json")',
    'print(\'{"type":"completed"}\');print(\'{"type":"partial","text":"extra"}\')',
    'print("x"*70000)',
])
def test_malformed_protocol(wav,monkeypatch,code):
    worker(monkeypatch,code)
    with pytest.raises(supervisor.SessionError,match="INVALID_PROTOCOL"):
        supervisor.run_wav(wav,timeout=5)

def test_deadline_terminates_owned_process(wav,monkeypatch):
    worker(monkeypatch,'import time;time.sleep(30)')
    started=time.monotonic()
    with pytest.raises(supervisor.SessionError,match="SESSION_TIMEOUT"):
        supervisor.run_wav(wav,timeout=0.4)
    assert time.monotonic()-started<5
    assert not supervisor._SINGLE_SESSION.locked()

def test_cancel_with_partial(wav,monkeypatch):
    worker(monkeypatch,'import time;print(\'{"type":"partial","text":"ola"}\');time.sleep(30)')
    cancel=threading.Event()
    with pytest.raises(supervisor.SessionError,match="CANCELLED"):
        supervisor.run_wav(wav,timeout=5,cancel=cancel,on_event=lambda _:cancel.set())
    assert not supervisor._SINGLE_SESSION.locked()

def test_guard_and_concurrency(wav,monkeypatch):
    monkeypatch.setattr(supervisor,"game_active",lambda:True)
    with pytest.raises(supervisor.SessionError,match="GAMEGUARD_ACTIVE"):
        supervisor.run_wav(wav)
    assert supervisor._SINGLE_SESSION.acquire(blocking=False)
    try:
        with pytest.raises(supervisor.SessionError,match="SESSION_BUSY"):
            supervisor.run_wav(wav)
    finally:
        supervisor._SINGLE_SESSION.release()
