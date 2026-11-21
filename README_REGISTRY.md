# Ultron Voice — registry de perfil de voz

Arquivos locais (`local:///`) armazenam perfil de voz, histórico de geração e
metadados de engine. Nenhum dado sai do host.

- `registry/voices/*.json` — perfil de voz (id, origem, checksum, engine).
- `registry/history/*.jsonl` — gerações recentes (id, payload, saida, sha256).
- `logs/*.jsonl` — eventos operacionais.

Formato do perfil:

```json
{
  "id": "uuid",
  "name": "string",
  "source": "reference|design",
  "reference_audio": "local:///caminho.wav",
  "engine": "torch-vits",
  "created_at": "iso",
  "sha256": "checksum do arquivo de origem"
}
```
