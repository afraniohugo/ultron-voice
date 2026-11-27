"""Local TTS: Piper, Espeak or experimental Windows SAPI.

The real TTS backends speak through a CLI subprocess. For tests the pipeline
accepts a ``tts`` callable that writes a deterministic WAV, so no model is
downloaded and no network is touched.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

try:  # optional
    from pydub import AudioSegment
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
    output_dir: Path = Path(".")


class TTS:
    def synthesize(self, text: str, out_path: Path, config: TTSConfig) -> Path:
        raise NotImplementedError


class PiperTTS(TTS):
    def synthesize(self, text: str, out_path: Path, config: TTSConfig) -> Path:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(text)
            tmp_text = fh.name
        try:
            cmd = ["piper", f"--model={config.model}", "--output_file", str(out_path), tmp_text]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"piper falhou: {res.stderr}")
            return out_path
        finally:
            Path(tmp_text).unlink(missing_ok=True)


class EspeakTTS(TTS):
    def synthesize(self, text: str, out_path: Path, config: TTSConfig) -> Path:
        cmd = ["espeak", "-w", str(out_path), "-s", "140", text]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"espeak falhou: {res.stderr}")
        return out_path


def build_tts(config: TTSConfig) -> TTS:
    if config.engine == "piper":
        return PiperTTS()
    if config.engine == "espeak":
        return EspeakTTS()
    if config.engine == "sapi":
        from .sapi import SapiTTS
        return SapiTTS()
    if config.engine == "qwen3":
        from .neural_qwen import Qwen3LocalTTS
        return Qwen3LocalTTS()
    raise ValueError(f"Unknown local TTS engine: {config.engine}")
