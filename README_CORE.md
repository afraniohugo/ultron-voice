# Ultron Voice Core — engine catalogue, registry and CLI

Package local-first de áudio para agentes. Engine catalogue, serviço MCP (stdio)
e CLI minimal (infer, transcribe, check_health), sem dependências de rede e
sem segredos.

## Módulos

- `core/catalogue.py` —Registry de motores disponíveis (TTS/ASR/DUB) com
  requisitos, engine, enable-conditions e limite de GPU.
- `core/registry.py` —Perfil de voz (salvo localmente), histórico de geração.
- `core/health.py` —check_health: GPU ativa, engines prontos, ffmpeg.
- `mcp_server.py` —MC P (stdio/SSE): generate_speech, clone_voice, transcribe,
  describe_voice, design_voice, list_*, check_health.
- `cli/ultron-voice` --entrada principal (infer, transcribe, audiobook, dub,
  check_health).

## Regras de consumo

1. Nenhum modelo baixado sem autorização explícita do dono.
2. Saídas vocais em `.wav`/`.ogg` dentro do diretório de saida (padrao:
   `outputs/`), com metadados SHA-256.
3. `manifesto-engine.json` registra engine, origem, hash, VRAM/CPU usado.
4. Logs locais em `logs/`, formato JSON por evento.
