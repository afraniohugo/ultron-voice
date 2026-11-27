# Ultron Voice — F1: audiobook WAV nativo

Estado: IMPLEMENTADO EM BRANCH ISOLADA, não integrado à produção.
Host: OptimusPrime. Independente do VoiceStudio para **montagem de WAVs PCM**.

## Entrega verificável
- Usa Python padrão (wave) para concatenar capítulos de áudio PCM com mesma taxa, canais e profundidade.
- CLI aceita capítulos JSON inline ou via arquivo. Verifica o formato e só imprime OK se houver saída válida.
- Grava em arquivo temporário, valida o WAV e move de forma atômica para o destino. Falhas preservam o arquivo anterior.
- Registra SHA-256 e histórico SQLite quando configurado; não copia código do VoiceStudio nem usa APIs pagas.
- Capítulos em texto exigem engine TTS local. Piper **só** usa modelo .onnx absoluto já existente e explicitamente indicado; sem download implícito. GameGuard impede síntese durante Warzone.
- Incremento F1.1: Windows SAPI (Microsoft Maria Desktop) disponível como engine experimental `sapi` com `--tts-model` explícito. Não depende de VoiceStudio, usa somente CPU, não oferece a qualidade humana exigida para produção.
- WAV de entrada deve estar autorizado pelo operador, inclusive direitos de uso e consentimento para gravações vocais.

## Uso
Crie chapters.json com conteúdo semelhante a:

~~~json
[
  {"audio_path": "E:\\IA LOCAL\\GitHub\\ultron-voice\\tests\\fixtures\\sample_5s.wav"},
  {"audio_path": "E:\\IA LOCAL\\GitHub\\ultron-voice\\tests\\fixtures\\sample_5s.wav"}
]
~~~

Executar com Python do ambiente já instalado, sem alterar serviços:

~~~powershell
Set-Location 'E:\IA LOCAL\GitHub\wt-ultron-voice-native-audiobook-f1-20261122'
& 'E:\IA LOCAL\GitHub\ultron-voice\.venv\Scripts\python.exe' -m ultron_voice.cli audiobook --title 'Canario' --chapters-json '.\chapters.json' --registry '.\history.db' '.\audiobook_canario.wav'
~~~

## Limites desta etapa
- WAV PCM homogêneo; formatos diferentes exigem etapa posterior de conversão explícita.
- Oferece piloto funcional SAPI do Windows; **não** oferece voz humana de qualidade homologada, clonagem, design de voz, tradução, dublagem ou conversa em celular.
- Não integra automaticamente o Hermes/Studio. A PR #1 (MCP VoiceStudio) é independente desta F1.
- Não baixar modelos, criar cron/serviço/gateway, publicar mídia, mexer na main ou desinstalar o VoiceStudio.
- Próximo passo: engine TTS local de qualidade, com modelos/licenças conferidos e avaliação auditiva humana; só depois testar o caminho sem VoiceStudio desligando seu processo em canário controlado.

## Verificação
Testes focados: pytest -q tests/test_native_audiobook.py.
O ensaio gera WAVs de laboratório, valida checksum, CLI, erro sem falso sucesso, integridade de arquivos em falha, e gates GameGuard/modelo local. Não usa GPU nem rede.
