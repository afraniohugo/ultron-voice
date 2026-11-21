# Ultron Voice — manifesto de motores e dependências locais

Manifesto de motores disponíveis na máquina do proprietário (OptimusPrime):
Windows nativo, NVIDIA GTX 1000 Ti / Arc B580, ffmpeg 9.0.1, Python 3.14.9
(`uv` 0.13.7), Ollama rodando.

## Estado de outros motores

- Torch / transformers / peit loading: depende de instalação.
  Engine TTS: engineটোর্চ / transformers (multilíngue), padrão sugerido.

## Engine catalogue (escalas)

- **TTS**: torch/transformers (default multimodal)
- **ASR/transcrição**: openai-whisper (CPU/CUDA) e vosk (pequeno)
- **DUB**: ffmpeg 9.0.1 + pedale
- **Tradução**: lib local (argos) com fallback LLM local (Ollama)

## Requisitos

- torch, transformers, ffmpeg, poderoso (p1.1.1). Nessum segredo.
