# Ultron Voice F3 — Qwen3-TTS 0.6B local: CANARIO NEURAL REAL

Host: OptimusPrime | Data: 22/11/2026 22:xx BRT
Estado: IMPLEMENTADO E TESTADO EM BRANCH ISOLADA. Sem deploy, merge ou publicacao.
Dependencias da branch: PR #2 (WAV/audiobook SAPI) -> PR #3 (motor neural) -> F3.

## Resultado E2E medido

- Modelo oficial: Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice.
- Revisao imutavel: 85e237c12c027371202489a0ec509ded67b5e4b5.
- Licenca declarada no cartao oficial e confirmada via Hugging Face API: Apache-2.0.
- Pesos baixados no proprio OptimusPrime, modelo completo 2.498.386.873 bytes nos artefatos selecionados. Arquivos principais validados por SHA256 no recibo model_receipt.json.
- Diretoria: E:\IA LOCAL\models\ultron_voice\qwen3_tts_06b_customvoice
- Runtime separado: E:\IA LOCAL\tools\ultron_voice_neural\.venv (Python 3.12.10, qwen-tts 0.1.1, torch 2.15.0+cpu, soundfile 0.14.0).
- Zero CUDA/GPU; pytorch manual eager; sem flash-attn. SoX CLI indisponivel, mas nao bloqueou este canario.
- Manifest: E:\IA LOCAL\models\ultron_voice\qwen3_f3_manifest.json; escopo laboratory_only, speaker Ryan, language Portuguese, instruct vazio.
- Texto: 'Olá! Eu sou o Ultron Voice. Agora falo diretamente no seu computador.'
- Audiobook CLI gerou WAV de verdade em 92,35 segundos (inferencia + carregamento).
- Saida: E:\IA LOCAL\logs\ultron_voice\neural_f3_20261122\qwen3_ptbr_lab.wav
- Audio: 7,92 s, 24.000 Hz, mono, PCM16, 380.204 bytes; pico 0,54248; RMS 0,07448; nao silencioso.
- SHA256 WAV: 9f1e59f418eb12b5c8d2bea5928f8e716823387f6d65cbd47ee5d88baa6fe947.
- Transcricao Vosk PT-BR: 'olá eu sou o outro voz agora fala diretamente no seu computador'. Confundiu nome de marca. Nao se deve inferir naturalidade/acentuacao pela transcricao.
- Porta 127.0.0.1:3900 indisponivel em teste; nada utilizou VoiceStudio.
- Um teste separado confirmou a importacao de torch/qwen_tts em CPU sem usar GPU.

## Correcao F3 versus F2

O CustomVoice 0.6B NAO suporta controle de estilo por instruction, mesmo que API aceite argumento. Foi removido uso enganoso de instruct no worker; manifestos com instruct nao-vazio falham de modo explicito (NEURAL_06B_INSTRUCTION_UNSUPPORTED). Atualizada conferencia de speech_tokenizer/model.safetensors; HF implicit token desativado.
Fonte: implementacao oficial em Qwen3-TTS, metodo generate_custom_voice; ver notas de 0.6B.

## Condicoes para permanecer isolado

- Qwen 0.6B inclui speaker Ryan sem timbre nativo especificamente brasileiro: naturalidade PT-BR NAO HOMOLOGADA. Nao usar nos canais ainda.
- Nada de clonagem da voz propria sem amostra e consentimento, e nenhum modelo de terceiros com peso NC na producao.
- GameGuard bloqueia jobs com jogo ativo, reconsulta durante inferencia e antes de salvar.
- Pesos ficam fora do Git. Sem API, pagamento, cron, novos gateways ou reboot.
- Chatterbox Multilingual pt-BR, cartao MIT, modelo especializado regionalmente, e proximo candidato para comparativo auditivo com licencas e checkpoint revisados.
- Licencas e direitos dos assets devem ser confirmados por utilizacao final, nao apenas codigo.

## QA

- QA focado: pytest -q tests/test_neural_qwen_offline.py tests/test_native_audiobook.py tests/test_sapi_lab.py.
- Resultado: 33/33 PASS, compileall PASS, git diff --check PASS.
- E2E real executado via CLI com HF_HUB_OFFLINE=1 e TRANSFORMERS_OFFLINE=1. Resultado WAV valido, checksum, ASR Vosk PT-BR.
- Wheel offline e validacao PR draft sao registrados separadamente.

## Proximo passo unico

Receber avaliacao auditiva do WAV e montar uma comparacao A/B com Chatterbox Single Language PT-BR (modelo MIT; compartilhados decoders e licencas conferidos), mantendo Qwen e SAPI apenas como referencias. Nao divulgar em canais antes de homologacao de voz.
