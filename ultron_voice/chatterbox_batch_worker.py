"""One-shot F5 CPU batch worker: load Chatterbox once, synthesize 2-4 clips.

No network, user voice or persistent agent/daemon. Used only by validated
ChatterboxBatchTTS parent; all outputs are temporary and lab-scoped.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        return 2
    request = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    if (request.get("status") != "READY_FOR_ISOLATED_CHATTR_PTBR"
            or request.get("scope") != "laboratory_only"
            or request.get("language") != "pt"):
        return 3
    items = request.get("items")
    if (not isinstance(items, list) or not 2 <= len(items) <= 4
            or any(not isinstance(it, dict)
                   or not isinstance(it.get("text"), str)
                   or not 0 < len(it["text"]) <= 280 for it in items)):
        return 3
    source_dir = Path(request["source_dir"]).resolve(strict=True)
    model_dir = Path(request["model_dir"]).resolve(strict=True)
    reference = Path(request["reference_audio"]).resolve(strict=True)
    targets = [Path(it["output"]) for it in items]
    if (any(not t.is_absolute() or t.suffix.lower() != ".wav" for t in targets)
            or len({str(t) for t in targets}) != len(targets)):
        return 3
    sys.path.insert(0, str(source_dir))
    from chatterbox.tts import ChatterboxTTS
    import torch
    import soundfile as sf

    torch.set_num_threads(4)
    model = ChatterboxTTS.from_local(str(model_dir), "cpu")
    with torch.inference_mode():
        for it, target in zip(items, targets):
            wave_tensor = model.generate(
                it["text"],
                audio_prompt_path=str(reference), language_id="pt",
                exaggeration=float(request["exaggeration"]),
                cfg_weight=float(request["cfg_weight"]),
                temperature=float(request["temperature"]),
            )
            samples = wave_tensor.squeeze(0).detach().to("cpu").numpy()
            if len(samples) == 0 or not 8000 <= int(model.sr) <= 48000:
                return 4
            sf.write(str(target), samples, int(model.sr), subtype="PCM_16")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception:
        raise SystemExit(5)
