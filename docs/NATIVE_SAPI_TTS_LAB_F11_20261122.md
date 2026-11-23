# Ultron Voice — F1.1 TTS PT-BR completamente local (LAB)

Data: 22/11/2026 | Host: OptimusPrime
Escopo: branch isolada da PR #2, sem merge, deploy ou servicos.

## Resultado real (nao apenas mock)
- Engine TTS sapi usa System.Speech.Synthesis nativo do Windows; selecao explicita Microsoft Maria Desktop (pt-BR).
- Sem processo, CLI, biblioteca, endpoint ou arquivos do VoiceStudio.
- No canario, 127.0.0.1:3900 estava sem listener; nenhum backend VoiceStudio foi iniciado.
- SAPI gerou WAV 16000 Hz, mono, 16-bit, com checksum, preservacao atomica e historico local.
- Audiobook CLI a partir de 2 capitulos em texto: 20,75 segundos, 663.948 bytes, RMS de 2077 (nao silencioso).
- WAV: E:\IA LOCAL\logs\ultron_voice\canary_20261122\ultron_voice_lab.wav
- SHA256: 512f41de42c92ddbf4f777eb53f638cbd32af98b7814ea2be041b2f5979694b3
- Vosk PT instalado transcreveu a maior parte da locucao via CPU, sem download e sem ffmpeg.
- HF_HUB_OFFLINE=1 e TRANSFORMERS_OFFLINE=1 ativos no ensaio; nenhum modelo adquirido.
- SAPI lab: NAO HOMOLOGADO para qualidade vocal/publicacao comercial. Microsoft Maria tem timbre sintetico.

## Comando de repeticao (na worktree)
~~~powershell
Set-Location 'E:\IA LOCAL\GitHub\wt-ultron-voice-native-audiobook-f1-20261122'
$env:HF_HUB_OFFLINE='1'
& 'E:\IA LOCAL\GitHub\ultron-voice\.venv\Scripts\python.exe' -m ultron_voice.cli audiobook --title 'Canario Ultron Voice' --chapters-json 'E:\IA LOCAL\logs\ultron_voice\canary_20261122\chapters.json' --tts-engine sapi --tts-model 'Microsoft Maria Desktop' --registry 'E:\IA LOCAL\logs\ultron_voice\canary_20261122\canary_history.db' 'E:\IA LOCAL\logs\ultron_voice\canary_20261122\ultron_voice_lab.wav'
~~~

## Licencas e rumo para voz natural
- SAPI e uma prova de interoperabilidade do Windows, nao uma escolha final de qualidade.
- Modelos k2-fsa/OmniVoice e GGUF sao encontrados no cache local. O codigo upstream pode ser Apache-2.0, mas os pesos indicam CC-BY-NC-4.0 no cartao do repositorio GGUF; NAO usar para narracao de afiliados/comercial sem permissao adequada. Ver: https://huggingface.co/Serveurperso/OmniVoice-GGUF
- Avaliar outros pesos de TTS PT-BR com licenca comercial apropriada e performance na GTX 1070 Ti ou CPU, antes de instala-los. Licenca do codigo nao basta; exigir licenca do modelo/pesos e voz.
- Usar propria voz para clonagem somente com gravacao/referencia e consentimento do titular; nenhuma referencia foi fornecida neste canario.

## GATES
- Check de GameGuard antes da sintese e a cada capitulo; falha na deteccao bloqueia.
- Render SAPI nao usa GPU e nao cria servidor, task, cron ou rede.
- Geracao no WAV revisavel; nenhuma publicacao. Sem baixar componentes nem tocar VoiceStudio.
- Testes SAPI reais + Vosk ASR, alem de casos negativos e testes anteriores: pytest -q tests/test_native_audiobook.py tests/test_sapi_lab.py.

## Proximo passo unico
Implementar um adaptador TTS direto para modelo neural PT-BR com pesos e licença comercial verificados, sem dependencia de VoiceStudio, medir naturalidade com comparacao auditiva e integrar ao MCP Hermes sem servicos duplicados. NAO desinstalar VoiceStudio agora.
