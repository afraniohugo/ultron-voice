# Ultron Voice

Repositorio de operações para a solução **Ultron Voice** — famílias de voz,
texto para fala, transcrição, dublagem de vídeo e audiobook em 100% local no
OptimusPrime (Windows nativo, NVIDIA GTX 1000 Ti/Arc B580, ffmpeg 9.0.1,
Python 3.14.9 com `uv`).

## O que vale a pena

- Render local de voz (clone + design) e áudio, com engine catalogue;
- transcrição/dictação, tradução local + dublagem de vídeo;
- MCP (stdio/SSE) como ponte para agentes; CLI própria `ultron-voice`;
- Registry de perfil de voz, histórico de geração e checkpoints locais.

## Regras de operação

1. Tudo roda local — nenhuma chamada a serviço pagos, nenhuma chave/credencial.
2. Nenhum novo cron, job, publicador ou canal concorrente. Não há duplicação de
   servidores ou cadeias de entrega existentes.
3. Cada gravação de código passa por branch/worktree, testes focados,
   PR draft, revista e receita independente.
4. Reprodução/render de jogos ou produção ativa entram em pausa.
5. Saídas: texto, JSON puro, áudio em caminhos dados; nenhum segredo versionado.

## Perfis

- **my** (dono) — agente executor local, detalhe de verificação.
- **ultron** — programa que orquestra e valida o fluxo de áudio.

## Perguntas a respoder

1. Qual engine TTS para produção: torch/transformers (multilíngue) ou MiniMax-H3
   local? (Exclusão de credenciais/keys, somente modelos próprios ou abertos.)
2. Modelo de REGRA de voz: clone-only (zero-shot) ou inclusive models
   "design-voice" pré-treinados locais?
3. Específico de dublagem: sync TV (ffmpeg), modelo de voz em gestos?

[Otimo, na propria ramificacao de desenvolvimento]
