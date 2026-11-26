"""All test model leases use temporary directories, never production paths."""
import pytest
from ultron_voice import model_lock

@pytest.fixture(autouse=True)
def isolate_model_lock(monkeypatch,tmp_path):
    monkeypatch.setattr(model_lock,"DEFAULT_LOCK",tmp_path/"model.pid")
