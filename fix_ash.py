from pathlib import Path

def rp(name, old, new):
    p = Path(name)
    s = p.read_text(encoding="utf-8")
    if old not in s:
        print("MISS", name); return
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print("OK", name)

# catalogue: notas dos motores
rp("ultron_voice/core/catalogue.py",
   "Instalar: uv sync -e .[asr]",
   "Engine: backend/engine/asr. Instalar: uv sync -e .[asr]")

# health: import + logica de prontidao
p = Path("ultron_voice/core/health.py")
s = p.read_text(encoding="utf-8")
if "import importlib.util" not in s:
    s = s.replace("import shutil\nimport subprocess\nimport sys\n",
                  "import shutil\nimport subprocess\nimport sys\nimport importlib.util\n")
lines = s.split("\n")
out = []
i = 0
while i < len(lines):
    ln = lines[i]
    if ln.strip() == 'if name == "whisper":':
        out += [
            '    if name == "whisper":',
            '        whisper_ok = importlib.util.find_spec("whisper") is not None',
            '        ready = whisper_ok and torch is not None',
            '        return {"ready": ready, "note": "openai-whisper pronto (torch + openai-whisper)." if ready else "openai-whisper nao instalado (uv sync -e .[asr])"}',
        ]
        i += 2
        continue
    if ln.strip() == 'if name == "vosk":':
        out += [
            '    if name == "vosk":',
            '        vosk_ok = importlib.util.find_spec("vosk") is not None',
            '        return {"ready": vosk_ok, "note": "vosk pronto." if vosk_ok else "vosk nao instalado (uv sync -e .[asr])"}',
        ]
        i += 2
        continue
    out.append(ln)
    i += 1
p.write_text("\n".join(out), encoding="utf-8")
print("OK", "ultron_voice/core/health.py")
