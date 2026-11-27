"""Offline neural TTS worker for the optional isolated Python 3.12 environment.

Run only as a subprocess of Qwen3LocalTTS after all local-artifact checks.
No VoiceStudio integration, web endpoints, API credentials, or GPU access.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        return 2
    request = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    if request.get("status") != "READY_FOR_ISOLATED_LOCAL_CANARY":
        return 3
    if request.get("source_model") != "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice":
        return 3
    if request.get("scope") != "laboratory_only":
        return 3
    if request.get("weights_license") != "Apache-2.0":
        return 3
    if request.get("language") != "Portuguese":
        return 3
    model_dir = Path(request["model_dir"]).resolve(strict=True)
    output = Path(request["output"])
    if not model_dir.is_dir() or not output.is_absolute():
        return 3
    from qwen_tts import Qwen3TTSModel
    import torch
    import soundfile as sf

    model = Qwen3TTSModel.from_pretrained(
        str(model_dir),
        device_map="cpu",
        dtype=torch.float32,
        attn_implementation="eager",
        local_files_only=True,
    )
    wavs, sr = model.generate_custom_voice(
        text=request["text"],
        language=request["language"],
        speaker=request["speaker"],
        instruct=request["instruct"],
    )
    if len(wavs) == 0 or sr < 8000:
        return 4
    sf.write(str(output), wavs[0], sr, subtype="PCM_16")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception:
        # No text, path, or credentials to stdout/stderr.
        raise SystemExit(5)
