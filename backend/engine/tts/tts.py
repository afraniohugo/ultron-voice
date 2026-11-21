"""Ultron Voice — Local TTS: Piper (default) ou Espeak.

The real TTS backends speak through a CLI subprocess. For tests the
pipeline accepts a ``tts`` callable that writes a deterministic WAV, so no
model is downloaded and no network is touched.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

try:  # optional
    from pydub import AudioSegment  # type: ignore
except ImportError:  # pragma: no cover
    AudioSegment = None

try:  # optional
    import ffmpeg  # type: ignore
except ImportError:  # pragma: no cover
    ffmpeg = None


@dataclass(frozen=True)
class TTSConfig:
    engine: str = "piper"
    model: str = "pt_BR-polyglot-medium"
    output_dir: Path = Path("outputs")
    speed: float = 1.0
    tts_callable: callable | None = None  # para testes, sem modelo baixado


class TTS:
    """Interface minima de um motor local de voz."""

    def synthesize(self, text: str, out_path: Path, config: TTSConfig) -> Path:
        raise NotImplementedError


class PiperTTS(TTS):
    """Backend cli: piper (modelosvoices em PT-BR)."""

    def synthesize(self, text: str, out_path: Path, config: TTSConfig) -> Path:
        import tempfile

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if config.tts_callable is not None:
            return config.tts_callable(text, out_path, config)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(text)
            tmp_text = fh.name
        try:
            cmd = [
                "piper",
                f"--model={config.model}",
                "--output_file",
                str(out_path),
                tmp_text,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"piper falhou: {res.stderr}")
            return out_path
        finally:
            Path(tmp_text).unlink(missing_ok=True)


class EspeakTTS(TTS):
    """Backend cli: espeak (legivel, sem modelo)."""

    def synthesize(self, text: str, out_path: Path, config: TTSConfig) -> Path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if config.tts_callable is not None:
            return config.tts_callable(text, out_path, config)
        cmd = ["espeak", "-w", str(out_path), "-s", str(int(140 * config.speed)), text]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"espeak falhou: {res.stderr}")
        return out_path


def build_tts(config: TTSConfig) -> TTS:
    return PiperTTS() if config.engine == "piper" else EspeakTTS()
