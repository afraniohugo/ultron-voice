import os
import pytest
from ultron_voice.model_lock import ModelLock,ModelLockTimeout,ModelLockError

def test_exclusive_and_owner_only_release(tmp_path):
    p=tmp_path/"model.pid"
    a,b=ModelLock(p),ModelLock(p)
    a.acquire(timeout=0)
    try:
        assert a.owner==os.getpid()
        b.release()
        assert p.exists()
        with pytest.raises(ModelLockTimeout): b.acquire(timeout=0)
    finally: a.release()
    assert not p.exists()
    b.acquire(timeout=0)
    b.release()
    assert not p.exists()

def test_stale_lease_never_stolen(tmp_path):
    p=tmp_path/"model.pid"
    p.write_text("999999999")
    with pytest.raises(ModelLockTimeout): ModelLock(p).acquire(timeout=0)
    assert p.read_text()=="999999999"

def test_io_error_fails_closed(tmp_path):
    p=tmp_path/"not-directory"
    p.write_text("x")
    with pytest.raises(ModelLockError): ModelLock(p/"model.pid").acquire(timeout=0)

def test_test_flag_does_not_disable_guard(monkeypatch,tmp_path):
    monkeypatch.setenv("ULTRON_VOICE_TEST_MODE","1")
    lock=ModelLock(tmp_path/"model.pid")
    with lock:
        assert lock.owner==os.getpid()
