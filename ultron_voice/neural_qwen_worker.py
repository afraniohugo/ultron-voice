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

    # Device from config, default to xpu if available (matching Chatterbox pattern)
    requested_device = request.get("device", "xpu")
    # Auto-detect XPU availability and fallback to CPU if needed
    use_xpu = False
    if requested_device == "xpu":
        try:
            import intel_extension_for_pytorch as ipex  # noqa: F401
            if hasattr(torch, "xpu") and torch.xpu.is_available():
                use_xpu = True
        except Exception:
            pass
    elif requested_device in ("cpu", "auto"):
        use_xpu = False
    else:
        use_xpu = False

    # Load the model on CPU first; XPU placement failures are eligible for CPU retry.
    try:
        model = Qwen3TTSModel.from_pretrained(
            str(model_dir),
            device_map="cpu",
            dtype=torch.float32,
            attn_implementation="eager",
            local_files_only=True,
        )
    except Exception:
        return 6

    try:
        if use_xpu:
            model.model = model.model.to("xpu")
            # Update cached device property so processor creates tensors on XPU.
            model.__dict__["device"] = torch.device("xpu")

        wavs, sr = model.generate_custom_voice(
            text=request["text"],
            language=request["language"],
            speaker=request["speaker"],
            # This checkpoint does not implement instruction control.
        )
    except Exception:
        # Exit 5 uniquely signals a failure after XPU was selected.
        return 5 if use_xpu else 6

    if len(wavs) == 0 or sr < 8000:
        return 4
    try:
        sf.write(str(output), wavs[0], sr, subtype="PCM_16")
    except Exception:
        return 6
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception:
        # No text, path, or credentials to stdout/stderr.
        raise SystemExit(6)