"""Headless controller tests; never instantiates Tk or opens a microphone."""
import threading
import pytest
from ultron_voice import asr_gui

def test_controller_completion(monkeypatch):
    def fake(path, *, language, cancel, on_event):
        assert path == "test.wav" and language == "pt"
        on_event({"type":"partial","text":"ola"})
        return {"status":"completed","text":"ola","events":2}
    monkeypatch.setattr(asr_gui,"run_wav",fake)
    c=asr_gui.SessionController()
    c.start("test.wav")
    c.thread.join(timeout=3)
    assert not c.active
    assert c.events.get_nowait()["type"]=="partial"
    assert c.events.get_nowait()["status"]=="completed"

def test_controller_cancel_and_busy(monkeypatch):
    started=threading.Event()
    def fake(path, *, language, cancel, on_event):
        started.set()
        assert cancel.wait(3)
        raise asr_gui.SessionError("ASR_CANCELLED")
    monkeypatch.setattr(asr_gui,"run_wav",fake)
    c=asr_gui.SessionController()
    c.start("test.wav")
    try:
        assert started.wait(2)
        with pytest.raises(asr_gui.SessionError,match="BUSY"):
            c.start("test.wav")
    finally:
        c.cancel()
        c.thread.join(timeout=4)
    assert not c.active
    assert c.events.get_nowait()=={"status":"error","code":"ASR_CANCELLED"}

def test_no_internal_exception_details(monkeypatch):
    def fake(*args,**kwargs):
        raise ValueError("private path")
    monkeypatch.setattr(asr_gui,"run_wav",fake)
    c=asr_gui.SessionController()
    c.start("test.wav")
    c.thread.join(timeout=3)
    assert c.events.get_nowait()=={"status":"error","code":"ASR_LOCAL_ERROR"}
