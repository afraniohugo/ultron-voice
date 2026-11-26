"""Half-duplex state and capture lifecycle with inert child processes."""
import sys
import threading
import time
import pytest
from ultron_voice import audio_turns as turns
from ultron_voice import capture_lab as capture

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(turns,"game_active",lambda:False)
    monkeypatch.setattr(capture,"game_active",lambda:False)
    monkeypatch.setattr(capture,"audio_turns",turns.AudioTurns(tail_seconds=0.05))

def test_playback_tail_and_exclusion():
    gate=turns.AudioTurns(tail_seconds=0.05)
    with gate.lease("playback",consent=True):
        assert gate.state=="playback"
        with pytest.raises(turns.AudioTurnError,match="BUSY"):
            with gate.lease("capture",consent=True): pass
    assert gate.state=="echo_tail"
    with pytest.raises(turns.AudioTurnError,match="ECHO_TAIL"):
        with gate.lease("capture",consent=True): pass
    time.sleep(0.07)
    with gate.lease("capture",consent=True):
        with pytest.raises(turns.AudioTurnError,match="BUSY"):
            with gate.lease("playback",consent=True): pass
    assert gate.state=="idle"

def test_consent_and_explicit_device(monkeypatch):
    monkeypatch.setattr(capture,"_command",lambda *a:pytest.fail("unexpected spawn"))
    with pytest.raises(turns.AudioTurnError,match="CONSENT"):
        capture.capture_pcm("Microphone")
    for device in ("", "default", "audio=other", "x:video=y"):
        with pytest.raises(turns.AudioTurnError,match="DEVICE"):
            capture.capture_pcm(device,consent=True)
    with pytest.raises(ValueError,match="LIMIT"):
        capture.capture_pcm("Microphone",seconds=31,consent=True)

def test_guard_before_capture(monkeypatch):
    monkeypatch.setattr(turns,"game_active",lambda:True)
    monkeypatch.setattr(capture,"_command",lambda *a:pytest.fail("unexpected spawn"))
    with pytest.raises(turns.AudioTurnError,match="GAMEGUARD"):
        capture.capture_pcm("Fixture",consent=True)

def test_real_inert_process_pcm(monkeypatch):
    monkeypatch.setattr(capture,"_command",lambda *a:[
        sys.executable,"-c","import sys;sys.stdout.buffer.write(b'\\x01\\x00'*16000)"])
    pcm=capture.capture_pcm("Fixture",seconds=1,consent=True)
    assert len(pcm)==32000
    assert capture.audio_turns.state=="idle"

def test_cancel_stops_owned_child(monkeypatch):
    monkeypatch.setattr(capture,"_command",lambda *a:[
        sys.executable,"-c","import time;time.sleep(30)"])
    cancel=threading.Event()
    timer=threading.Timer(0.3,cancel.set)
    timer.start()
    try:
        with pytest.raises(turns.AudioTurnError,match="CANCELLED"):
            capture.capture_pcm("Fixture",seconds=1,consent=True,cancel=cancel)
    finally:
        timer.cancel()
    assert capture.audio_turns.state=="idle"

def test_invalid_pcm_fails_closed(monkeypatch):
    monkeypatch.setattr(capture,"_command",lambda *a:[
        sys.executable,"-c","import sys;sys.stdout.buffer.write(b'x')"])
    with pytest.raises(turns.AudioTurnError,match="INVALID_PCM"):
        capture.capture_pcm("Fixture",seconds=1,consent=True)
    assert capture.audio_turns.state=="idle"
