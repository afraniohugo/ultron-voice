"""Bounded CLI worker lifecycle tests without hardware or model downloads."""
import io
import json
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import pytest
from ultron_voice import asr_stream_cli as cli

class BlockedReader:
    def __init__(self):
        self.release = threading.Event()
    def read(self,n):
        self.release.wait(5)
        return b""

def test_idle_pipe_times_out():
    source=BlockedReader()
    try:
        with pytest.raises(cli.StreamIdleTimeout):
            list(cli.timed_pcm_blocks(source,idle_timeout=0.15))
    finally:
        source.release.set()

def test_cancelled_pipe_exits():
    source=BlockedReader()
    stop=threading.Event()
    stop.set()
    try:
        with pytest.raises(cli.StreamCancelled):
            list(cli.timed_pcm_blocks(source,idle_timeout=5,cancelled=stop))
    finally:
        source.release.set()

def test_cancelled_session_no_completion(monkeypatch):
    cancelled=threading.Event()
    def stream(blocks,language):
        for block in blocks:
            cancelled.set()
            yield {"type":"final","text":"must not publish"}
    monkeypatch.setattr(cli,"create_engine",lambda _:SimpleNamespace(transcribe_stream=stream))
    out,err=io.StringIO(),io.StringIO()
    code=cli.run(SimpleNamespace(pcm_stdin=True,language="pt"),
                 stdin=io.BytesIO(b"\0\0"),stdout=out,stderr=err,cancelled=cancelled)
    assert code==1 and out.getvalue()==""
    assert json.loads(err.getvalue())["code"]=="ASR_CANCELLED"

def test_worker_hard_deadline():
    # Dedicated subprocess with deliberately stuck Python decoder, no real model.
    script=("from ultron_voice import asr_stream_cli as m; "
            "from types import SimpleNamespace as S; import time; "
            "m.run=lambda *a,**k:time.sleep(30); "
            "m.run_worker(S(session_timeout=0.2))")
    result=subprocess.run([sys.executable,"-c",script],capture_output=True,timeout=8)
    assert result.returncode==124
    assert b"ASR_SESSION_TIMEOUT" in result.stderr
    assert b"completed" not in result.stdout

def test_library_main_does_not_use_hard_exit(monkeypatch):
    from ultron_voice import cli as entry
    monkeypatch.setattr(cli,"run",lambda args: 7)
    monkeypatch.setattr(cli,"run_worker",lambda args: pytest.fail("hard exit in library"))
    assert entry.main(["asr-stream","--pcm-stdin"])==7
