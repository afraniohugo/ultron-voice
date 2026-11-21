# ARCHITECTURE — Ultron Voice

Copy-left da stack upstream `debpalash/voicestudio` (VoiceStudio / OmniVoice-Studio),
em nova forma de aplicação: o cliente opera localmente, com MCP como entrada de
agentes, e não serve em nuvem.

## Entradas e saídas

- Entrada: texto, referência de voz (arquivo/base64), áudio para transcrição e
  dublagem.
- Saída: áudio (`.wav/.ogg`), texto, JSON puro, logs locais. Nenhuma saída contém
  chave, token ou credencial.

## Camadas

```
MCP (stdio/SSE) → CLI + FastAPI (lessons) → Engines (TTS/ASR/DUB) → Modelos + ffmpeg
```

## Módulos

- `mcp_server.py` — ferramentas obsolescentes (generate_speech, clone_voice,
  transcribe, list_, describe_voice, design_voice, check_health), recursos de
  voz/histórico, modo `resources|files|both`.
- `cli/ultron-voice` — infer, infer-batch, dub, audiobook, transcribe.
- `engines/` — catalogo de motores local (torch/transformers, whisper/vosk,
  Ollama, ffmpeg), roteamento de GPU/CPU.
- `audio/` — DSP, ffmpeg, segmentação de fala, sincronização de video.
- `registry/` — perfil de voz, histórico, backup local.
- `docs/` — revisões de decisão, roadmap, bugs abertos.
```

## Regra de negócio

- Nenhum material remoto; nenhum acesso a produção.
- Render gerado salvo em `E:\IA LOCAL\notas\ultron-voice\outputs\`
  (ou caminho configurável), com checksum SHA-256 e metadados.
```

## Licença e transferência

- Código distribuído agrega original da stack upstream (AGPL-3.0), em repositório
  da própria licença, e modelo de alta qualidade (OmniVoice, Apache-2.0) dentro do
  modelo.
- A decisão do dono decide reutilização independente da licença; o risco de
  remissão encontra-se registrado no dossiê de reversão de
  `notas/ultron-voice/reversao-dossier.md`.
```

## Validação

- `make lint` (style) e `make test` (focos, sem pytest duplicados).
- Render de amostra e aquisição de checksum; logs de auditoria separados.
