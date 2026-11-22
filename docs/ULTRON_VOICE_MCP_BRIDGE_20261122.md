# Ultron Voice — MCP original para o ecossistema AFRANTECH
Data: 2026-11-22 | Host: OptimusPrime | Estágio: canário, não produção comercial.

## Preservação da ideia do proprietário
- **VoiceStudio 0.5.8** é a aplicação instalada pelo proprietário e a referência de recursos/UX, preservada sem alterações.
- **Ultron Voice** é implementação própria da AFRANTECH; o MCP chama a CLI pública local do VoiceStudio, sem copiar código, mudar licença, extrair modelos protegidos ou alterar perfis.
- **Ultron Studio** mantém controle da timeline, dos direitos e da publicação; continua independente na porta 8779, sem modificações de código.
- Os modelos Kokoro/MOSS, baixados em laboratórios anteriores, **não substituem** a seleção de vozes. Perfis são escolhidos explicitamente após avaliação humana.

## MCP via STDIO
- Entrypoint: `mcp_server.py` ou `python -m ultron_voice.mcp`.
- Interpreter já existente: `E:\IA LOCAL\GitHub\ultron-voice\.venv\Scripts\python.exe`.
- Ferramentas: `check_health`, `start_voice_backend`, `list_voices`, `list_engines`, `list_languages`, `list_personalities`, `generate_speech`, `transcribe`, `describe_voice`, `design_voice`, `clone_voice`, `studio_audio_handoff`.
- O backend VoiceStudio existente (não um clone) atende somente `http://127.0.0.1:3900`. Para sessões locais reproduzíveis pode subir headless pelo MCP. Variável `ULTRON_VOICE_AUTOSTART_BACKEND=1` permite reinicialização sob demanda do backend existente, sem criar Windows Task, gateway ou cron.
- O Studio cataloga áudio gerado em `E:\IA LOCAL\producoes\ultron_studio\audio_assets\ultron_voice_drafts`; `studio_audio_handoff` confere SHA256, id e classificação `STAGING_UNVERIFIED`.
- Texto, perfis, caminhos e idioma validados; sem shell ao executar CLI; GameGuard impede novos jobs e cancela processos em andamento; diretórios de entrada limitados. Voz não é escolhida por default.
- `clone_voice` requer consentimento explícito e continua sujeito ao consentimento nativo/obrigações de licença; nunca autoriza voz comercial automaticamente.
- **Todas as saídas são DRAFT_REVIEW_REQUIRED, rights_verified=false, publication_allowed=false.** O Studio mantém proibição de mixagem, vinculação de fontes e publicação sem grants e QA.
- Para usar em Hermes, registrar `ultron_voice` por CLI oficial usando Python acima, script MCP da branch em homologação e variável `ULTRON_VOICE_AUTOSTART_BACKEND=1`. Não registrar um segundo VoiceStudio MCP concorrente.
- Após merge homologado, apontar o Hermes para `E:\IA LOCAL\GitHub\ultron-voice\mcp_server.py`. Até lá, branch isolada do repositório original.
- Teste real: SDK MCP 12 ferramentas, VoiceStudio CLI sobre localhost, gera WAV com demo `demo0001`, Studio encontra source_id e transcrição local responde. A voz do demo é inadequada para publicação; teste é funcional, não artístico.
- Rollback Hermes: `hermes mcp remove ultron_voice` se disponível (consultar ajuda), ou restaurar config do backup antes do cadastro; manter projetos e arquivos inalterados.
- Backups de config Hermes contêm dados possivelmente sensíveis: armazenar exclusivamente junto ao config original com ACLs, jamais versionar, sincronizar ao Drive ou exibir.
- **Pendências preservadas**: dublagem, audiobook, tradução, qualidade artística, vozes humanas, MIDI/SFX; não afirmar conclusão dessas frentes porque não fazem parte do canário MCP.
