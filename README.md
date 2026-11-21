# Ultron Voice

Inteligência artificial local de voz e áudio, projeto afrantech-hermes.
Curadoria autoral — versão própria do repositório upstream `debpalash/voicestudio`
(OmniVoice-Studio / VoiceStudio), operável 100% local, com MCP (stdio + SSE),
CLI e pipeline de dublagem a partir de modelos e ferramentas da máquina.

## Princípios

- **100% local.** Nenhum serviço remoto, modelo pago, API-chave ou cobrança ativada.
  Todo o processamento roda no host do proprietário (OptimusPrime).
- **Voz própria.** Clonagem zero-shot, design de voz e TTS com engine catalogue.
- **Licença.** Rascunho AGPL-3.0, com apontamento à obra upstream (VoiceStudio,
  AGPL-3.0; modelos OmniVoice Apache-2.0). O dono assume o risco de reutilização
  independente da licença conforme medio da decisão nom_demais.
- **Trazer **sem**ajuda de nuvem. Documentos, browser, navegação e integrações
  externos passam pelo dono ou sao explicitamente autorizados em cada missao.

## Pilares

1. **MCP** (stdio + SSE) — a interface principal para agentes.
2. **Engine catalogue** — TTS/ASR/DUB selecionados por metadados e disponibilidade.
3. **CLI** — `uv run ultron-voice infer | dub | audiobook | transcribe`.
4. **Demo** — controle rápido e verificação de qualidade local.

## Estrutura

```
ultron-voice/
├─ backend/   # FastAPI app do servico (lessons)
├─ mcp_server.py   # MCP stdio+SSE (servidor)
├─ cli/       # CLI (uv run ultron-voice ...)
├─ engines/   # Engines locales, catalogo e balanceamento
├─ audio/     # DSP, encoding (ffmpeg/opus), pipeline de dub
├─ tests/     # Tests focados e checks nao-redundantes
└─ docs/      # Arquivos de decisao e referencia
```

## Entrada e saida de dados (modelo de mensagem)

- Entrada: texto, perfil de voz (id/base64 audio), caminho de audio para
  transcricao/dub, metadados de projeto.
- Saidas: .wav/.ogg em caminho seguro, JSON puro (nunca JSON misturado a
  base64 grande), logs de auditoria locais.

## Imutabilidade do material de referencia

O repositorio upstream `debpalash/voicestudio` (OmniVoice-Studio / VoiceStudio)
e a fonte de referencia. Isso nao altera a licenca: o upstream permanece AGPL-3.0
na propria copia, e a distribuicao de Ultron Voice segue as condicoes do AGPL-3.0
ou da licenca de cada componente adotado. Nenhum segredo, chave ou credencial e
incluido em nenhum arquivo deste repositorio.
