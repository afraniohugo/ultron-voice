"""F4 Chatterbox PT-BR local-only synthesis worker; private lab input.

Runs in a separate pinned Python 3.11 venv. Does not download models,
expose a server, access VoiceStudio, or load user voice references.
"""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
# Allow XPU; do not block Intel GPU
os.environ.pop("CUDA_VISIBLE_DEVICES", None)

def main(argv: list[str]) -> int:
    if len(argv) != 1:
        return 2
    doc = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    if doc.get("status") != "READY_FOR_ISOLATED_CHATTR_PTBR":
        return 3
    if doc.get("scope") != "laboratory_only" or doc.get("language") != "pt":
        return 3
    text = doc.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 280:
        return 3
    src = Path(doc["source_dir"]).resolve(strict=True)
    model_dir = Path(doc["model_dir"]).resolve(strict=True)
    reference = Path(doc["reference_audio"]).resolve(strict=True)
    output = Path(doc["output"])
    if not output.is_absolute() or output.suffix.lower() != ".wav":
        return 3

    # Device from config, default to xpu if available
    device = doc.get("device", "xpu")

    # Pinned source from the official PT-BR Space, not the generic multilingual checkpoint.
    sys.path.insert(0, str(src))
    from chatterbox.tts import ChatterboxTTS
    import torch
    import soundfile as sf

    if device not in ("cpu", "xpu", "auto"):
        return 3
    if device != "cpu":
        device = "xpu" if hasattr(torch, "xpu") and torch.xpu.is_available() else "cpu"
    torch.set_num_threads(4)
    model = ChatterboxTTS.from_local(str(model_dir), device)
    with torch.inference_mode():
        wav = model.generate(
            text, audio_prompt_path=str(reference), language_id="pt",
            exaggeration=float(doc["exaggeration"]),
            cfg_weight=float(doc["cfg_weight"]),
            temperature=float(doc["temperature"]),
        )
    audio = wav.squeeze(0).detach().to("cpu").numpy()
    if not len(audio) or not 8000 <= int(model.sr) <= 48000:
        return 4
    sf.write(str(output), audio, int(model.sr), subtype="PCM_16")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception:
        # Never write model paths, environment details, or traceback to a shared file.
        raise SystemExit(5)