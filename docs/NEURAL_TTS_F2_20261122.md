# Ultron Voice F2 — adaptador neural Qwen3-TTS OFFLINE (LAB)

Data: 22/11/2026 | Host: OptimusPrime | Base: F1.1 / PR #2
Estado: CODIGO PREPARADO E TESTADO COM FIXTURES. INFERENCIA NEURAL REAL NAO TESTADA.
Sem merge, sem deploy, sem acesso a GPU, sem instalar pacotes ou pesos.

## Escolha e fontes oficiais

1. Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice: checkpoint oficial com metadado Apache-2.0; 10 idiomas (inclui Portuguese), instrucao de tom e vozes predefinidas; nao possui voz nativa de portugues brasileiro entre os nove perfis. Qualidade de sotaque PT-BR permanece NAO VERIFICADA.
   - https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
   - https://github.com/QwenLM/Qwen3-TTS
2. ResembleAI/Chatterbox-Multilingual-pt-br: MIT declarado, checkpoint afinado para portugues brasileiro, 2.143.990.296 bytes apenas no arquivo T3 e precisa de decoder e arquivos adicionais; candidato comparativo para avaliar naturalidade PT-BR. NAO instalado.
   - https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br
3. Pesos OmniVoice GGUF presentes no computador com indicacao anterior de CC-BY-NC (restricao comercial): EXCLUIDOS deste adaptador.
4. MIT e Apache-2.0 nos cartoes nao substituem revisao de avisos, direitos de voz/speaker e licencas de todos os checkpoints e dependencias antes de publicar narracoes comerciais.

## O que foi implementado

- Engine qwen3 no catalogo e na CLI audiobook, via --tts-engine qwen3 e --tts-model com caminho absoluto de manifesto JSON.
- Backend separado de CPU, sem VoiceStudio, sem porta 3900, sem API paga, sem modelo pelo identificador remoto.
- Modelo obrigatoriamente em E:\IA LOCAL\models\ultron_voice\ e Python em E:\IA LOCAL\tools\ultron_voice_neural\.
- Manifesto obriga id exato do checkpoint, declaracao de licenca Apache-2.0 revisada, speaker suportado, idioma Portuguese, e usage_scope laboratory_only.
- Preflight confere modelo local, arquivos essenciais e interpretador, bloqueia caminhos fora das raizes e pesos ausentes ANTES de iniciar processo.
- Worker subprocesso -I, apenas em CPU/eager/float32, com ambiente sem chaves e HF_HUB_OFFLINE=1. Processamento com timeout e GameGuard antes, durante e apos.
- Gera WAV PCM, salva em arquivo temporario e substitui atomicamente. Falha preserva o arquivo anterior; nao publica.
- Testes de contrato exercitam mock de worker, bloqueio de caminhos, licenca, jogo, arquivo incompleto, falha e CLI. Eles NAO equivalem a teste com modelo neural real.

## Configuracao futura, somente depois de instalacao autorizada

O manifesto JSON deve estar dentro de E:\IA LOCAL\models\ultron_voice (nao versionar dados pessoais, vozes ou pesos):

~~~json
{
  "source_model": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
  "weights_license": "Apache-2.0",
  "weights_license_reviewed": true,
  "usage_scope": "laboratory_only",
  "model_dir": "E:\\IA LOCAL\\models\\ultron_voice\\qwen3_tts_06b_customvoice",
  "runtime_python": "E:\\IA LOCAL\\tools\\ultron_voice_neural\\.venv\\Scripts\\python.exe",
  "language": "Portuguese",
  "speaker": "Ryan",
  "instruct": "Speak clearly in natural Brazilian Portuguese with warm, friendly rhythm."
}
~~~

O model_dir precisa conter pesos reais do checkpoint oficial, config.json, generation_config.json e speech_tokenizer/config.json. Dependencias qwen-tts devem ficar no Python 3.12 isolado, nao instaladas no Hermes Python 3.14. Ryan e nativo do ingles; portugues brasileiro nao homologado.

Exemplo de comando APENAS quando modelo/runtime estiverem instalados e conferidos:

~~~powershell
& 'E:\IA LOCAL\GitHub\ultron-voice\.venv\Scripts\python.exe' -m ultron_voice.cli audiobook --title 'Laboratorio Qwen' --chapters '[{"text":"Olá, este é um teste técnico."}]' --tts-engine qwen3 --tts-model 'E:\IA LOCAL\models\ultron_voice\manifest.json' 'E:\IA LOCAL\logs\ultron_voice\qwen_lab.wav'
~~~

## Criterios pendentes (nao considerar concluido)

- Baixar/instalar pesos e runtime apenas com autorizacao, hashes de artefatos e licencas validados.
- Rodar inferencia REAL offline em CPU e medir tempo/memoria; depois avaliar GPU sem competir com jogo/LoFi/Studio.
- Comparar locucao A/B Qwen vs Chatterbox PT-BR vs Microsoft Maria (lab) com audicao humana.
- Clonagem propria somente com audio e consentimento autorizado.
- So depois integrar ao MCP Hermes/Studio; nao tocar na PR #1 atual sem reconciliar dependencia de VoiceStudio.
- Sem producao, canais, VoiceStudio removido, merge ou reboot.
