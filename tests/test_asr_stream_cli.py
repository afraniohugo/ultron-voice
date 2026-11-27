"""Local ASR transport tests; no microphone or model required."""
import io
import json
import wave
from types import SimpleNamespace
import pytest
from ultron_voice import asr_stream_cli as cli

class ShortReads(io.BytesIO):
    def read(self,n=-1):
        return super().read(min(n,101))

def test_pipe_short_reads():
    data=b"\0\0"*4001
    assert b"".join(cli.pcm_blocks(ShortReads(data)))==data

def test_truncated_pipe():
    with pytest.raises(ValueError,match="TRUNCATED"):
        list(cli.pcm_blocks(io.BytesIO(b"x")))

def test_bounded_pipe(monkeypatch):
    monkeypatch.setattr(cli,"MAX_BYTES",10)
    with pytest.raises(ValueError,match="LIMIT"):
        list(cli.pcm_blocks(io.BytesIO(b"x"*12)))

def test_json_events_and_terminal(monkeypatch):
    def stream(blocks,language):
        assert language=="pt"
        assert b"".join(blocks)==b"\0\0"
        yield {"type":"partial","text":"ola"}
        yield {"type":"final","text":"ola mundo"}
    monkeypatch.setattr(cli,"create_engine",lambda _:SimpleNamespace(transcribe_stream=stream))
    out,err=io.StringIO(),io.StringIO()
    assert cli.run(SimpleNamespace(pcm_stdin=True,language="pt"),stdin=io.BytesIO(b"\0\0"),stdout=out,stderr=err)==0
    assert [json.loads(x)["type"] for x in out.getvalue().splitlines()]==["partial","final","completed"]
    assert not err.getvalue()

def test_error_has_no_success_terminal(monkeypatch):
    def stream(blocks,language):
        yield {"type":"partial","text":"ola"}
        raise RuntimeError("private internal path")
    monkeypatch.setattr(cli,"create_engine",lambda _:SimpleNamespace(transcribe_stream=stream))
    out,err=io.StringIO(),io.StringIO()
    assert cli.run(SimpleNamespace(pcm_stdin=True,language="pt"),stdin=io.BytesIO(),stdout=out,stderr=err)==1
    assert "completed" not in out.getvalue()
    assert "private" not in err.getvalue()

def test_wav_contract(tmp_path,monkeypatch):
    path=tmp_path/"sample.wav"
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(b"\0\0")
    monkeypatch.setattr(cli,"create_engine",lambda _:None)
    out,err=io.StringIO(),io.StringIO()
    assert cli.run(SimpleNamespace(pcm_stdin=False,wav=str(path),language="pt"),stdin=io.BytesIO(),stdout=out,stderr=err)==1
    assert not out.getvalue()

def test_truncated_wav(tmp_path,monkeypatch):
    path=tmp_path/"sample.wav"
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b"\0\0"*4)
    path.write_bytes(path.read_bytes()[:-2])
    def stream(blocks,language):
        list(blocks)
        yield {"type":"final","text":"ola"}
    monkeypatch.setattr(cli,"create_engine",lambda _:SimpleNamespace(transcribe_stream=stream))
    out,err=io.StringIO(),io.StringIO()
    assert cli.run(SimpleNamespace(pcm_stdin=False,wav=str(path),language="pt"),stdin=io.BytesIO(),stdout=out,stderr=err)==1
    assert "completed" not in out.getvalue()
