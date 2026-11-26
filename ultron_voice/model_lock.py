"""Exclusive local neural-model lease. Fail closed on contention or I/O error."""
from __future__ import annotations
import os
import time
from pathlib import Path

DEFAULT_LOCK = Path(r"E:\IA LOCAL\logs\ultron_voice\model_lock\model.pid")

class ModelLockError(RuntimeError):
    pass

class ModelLockTimeout(ModelLockError):
    pass

class ModelLock:
    """O_EXCL lease shared by CPU/XPU workers. Never kill a PID or steal a stale file.

    A leftover lease after a crash requires operator verification before removal.
    No runtime or environment variable can disable this guard.
    """
    def __init__(self, path: Path | None=None, *, heartbeat: float=5.0, stale_after: float=30.0):
        self.path=Path(path) if path is not None else DEFAULT_LOCK
        self._fd=None
        self._owner_pid=None

    def acquire(self, timeout: float=120.0) -> None:
        if self._fd is not None:
            raise ModelLockError("MODEL_LOCK_ALREADY_HELD")
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            raise ModelLockError("MODEL_LOCK_STORAGE_UNAVAILABLE") from exc
        deadline=time.monotonic()+max(0,timeout)
        while True:
            try:
                fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                break
            except FileExistsError:
                if time.monotonic()>=deadline:
                    raise ModelLockTimeout("MODEL_LOCK_BUSY_OR_STALE")
                time.sleep(.05)
            except OSError as exc:
                raise ModelLockError("MODEL_LOCK_STORAGE_UNAVAILABLE") from exc
        try:
            os.write(fd,f"{os.getpid()}\n".encode("ascii"))
            os.fsync(fd)
        except OSError as exc:
            os.close(fd)
            try: self.path.unlink()
            except OSError: pass
            raise ModelLockError("MODEL_LOCK_WRITE_FAILED") from exc
        self._fd=fd
        self._owner_pid=os.getpid()

    def release(self) -> None:
        if self._fd is None or self._owner_pid!=os.getpid():
            return
        fd=self._fd
        try:
            same=os.path.samestat(os.fstat(fd),self.path.stat())
        except OSError:
            same=False
        finally:
            os.close(fd)
            self._fd=None
            self._owner_pid=None
        if not same:
            raise ModelLockError("MODEL_LOCK_OWNERSHIP_CHANGED")
        self.path.unlink()

    @property
    def owner(self) -> int | None:
        return self._owner_pid

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self,*args):
        self.release()

def get_model_lock() -> ModelLock:
    return ModelLock()

def select_device(requested: str="auto") -> str:
    if requested=="cpu":
        return "cpu"
    if requested not in ("auto","xpu"):
        return "cpu"
    try:
        import torch
        if hasattr(torch,"xpu") and torch.xpu.is_available():
            return "xpu"
    except Exception:
        pass
    return "cpu"
