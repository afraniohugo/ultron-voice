# backend/engine — motor de transcricao local (ASR)

Motor de transcricao de audio para Ultron Voice. 100% local, sem servicos
remotos, sem segredos.

## Estrategia escolhida
- **Principal: vosk** - leve, roda sozinho em CPU, nao exige `torch` e
  suporta português do Brasil (`pt`) e inglês (`en`) via modelos
  `vosk-model-small-pt-0.3` / `vosk-model-small-en-us-0.15`.
- **Complementar: openai-whisper** (torch) - qualidade maior, mas mais
  pesado e exige `torch` (ver [Uso](#uso)).

## Estrutura
```
backend/engine/
  __init__.py            # API publica (transcribe, create_engine)
  asr/
    __init__.py          # registry + dispatch
    base.py              # interface ASREngine
    vosk_engine.py       # motor vosk (principal, validado)
    whisper_engine.py    # motor openai-whisper (complementar)
    README.md            # este arquivo
```

## Instalação
```
# Tudo o que o projeto declara
uv sync

# Só o grupo ASR (inclui openai-whisper e vosk)
uv sync -e ".[asr]"

# Para testar o motor whisper, adicione a dependencia torch
uv sync -e ".[local]"
```

## Uso
### Programaticamente
```python
from backend.engine.asr import transcribe

text = transcribe("consulta.wav", language="pt")   # texto em português
print(text)
```

### Pelo motor (vinculado ao catalogue)
```python
from backend.engine.asr import create_engine

engine = create_engine("vosk")
text = engine.transcribe("consulta.wav", language="pt")
```

### Pelo catalogue existente (ultron_voice.core.catalogue)
Os motores `whisper` e `vosk` já estão registrados. Depois de instalar o
grupo `[asr]`, o engine `vosk` fica pronto e a saída do `engines` do CLI
reflete a disponibilidade.

## Modelos
- **pt**: `vosk-model-small-pt-0.3` (~40 MB)
- **en**: `vosk-model-small-en-us-0.15` (~40 MB)

O modelo é baixado automaticamente na primeira transcrição e guardado em
`<home>/.ultron-voice/models` (ou `$ULTRON_VOICE_MODELS_DIR`).

## Teste
```
# gera um clip de audio de 5s e transcreve com vosk
uv run python -m ultron_voice.cli transcribe tests/fixtures/sample_5s.wav --lang pt
```

## Limitações
- O `vosk` (modelo pequeno) tem precisão inferior à `whisper`
  (modelo `tiny`+)/cloud. O objetivo é resolver a transcrição local em
  tempo real em máquinas modestas; para acurácia máxima, usar `whisper`
  com modelo `base`/`small` executa em GPU.
- O motor depende de `ffmpeg` estar presente no `PATH` (usado para
  normalizar a transcrição de áudio).
