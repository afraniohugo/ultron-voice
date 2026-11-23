# Ultron Voice F4 — Chatterbox PT-BR REAL (LAB)

Data 22/11/2026 | Host OptimusPrime | Status IMPLEMENTADO, TESTADO E ISOLADO; NAO MESCLADO/NAO PUBLICADO.

## Escopo

Motor TTS Chatterbox Multilingual V3 com fine-tune single-language PT-BR oficial.
Caminho unico: Ultron Voice CLI -> engine chatterbox_ptbr -> worker Python 3.11 isolado -> pesos PT-BR locais -> WAV PCM.
Nao depende do VoiceStudio. Nao cria servidor, cron, gateway, bot ou publicador.

## Proveniencia, pesos e codigo com hash fixo

- Modelo: ResembleAI/Chatterbox-Multilingual-pt-br rev b3952f18bc2eaa72b9bd7c17d2c4653bcad4770d. Cartao MIT.
- Pesos complementares: ResembleAI/chatterbox rev 5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18. Cartao MIT.
- Codigo: Hugging Face Space oficial ResembleAI/Chatterbox-Multilingual-TTS-pt-br rev 9e515821e826e207cd617a0fdd0223899ed108ea; derivado do Chatterbox original. Fonte nao copiada para Git.
- Todos os 5 arquivos principais tiveram bytes e SHA256 conferidos. Ver recibo: E:\IA LOCAL\logs\ultron_voice\chatterbox_f4_20261122\weights_receipt.json
- t3_pt_br.safetensors: 2.143.990.296 bytes, SHA256 074aaf65255eb9cb960288f7cc72e09d3b5008f6e0b14868c0d4e5b0bd7cbb6c
- s3gen_v3.pt: 1.056.903.694 bytes, SHA256 f7abce4b196dae2d08d9296cbebc6521b046079577643b42a19a03499d08721e
- Codigo-fonte Space: 45 arquivos .py, SHA256 de arvore ordenada 2d069415e18693bbe3cb850fd105b91d60cab923d44d7838622e3f2ef9c8adfa
- Codigos e pesos ficam em E:\IA LOCAL\tools\ultron_voice_chatterbox e E:\IA LOCAL\models\ultron_voice\chatterbox_ptbr; nada disso foi versionado no Git.
- Runtime separado: Python 3.11, torch 2.8.0+cpu, torchaudio 2.8.0+cpu, transformers 4.46.3, s3tokenizer 0.3.0, resemble-perth 1.0.1; setuptools fixado em 80.10.2 por dependencia do librosa/pkg_resources. NAO instalar no Hermes/Python principal.
- Em cada geracao, o preflight valida paths, licenca, revisoes, tamanhos e hashes dos 5 arquivos e codigo-fonte. O worker usa from_local, e HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE permanecem ativos.

## Referencia de voz e direitos

- Referencia EXCLUSIVA para este teste: Qwen3 WAV sintetico da F3, 7,92 s; hash 9f1e59f418eb12b5c8d2bea5928f8e716823387f6d65cbd47ee5d88baa6fe947.
- Nao foi usada gravacao humana. Nenhum perfil de voz do usuario foi criado/clonado.
- O motor conserva o watermark PerTh de origem; nunca remove ou contorna marcas.
- O manifesto exige reference_source=synthetic_qwen_lab e usage_scope=laboratory_only. Alteracao para voz humana, outro arquivo, uso comercial ou modelo nao autorizado falha fechada.
- Licenca MIT declarada dos pesos nao substitui auditoria de dependencias e direitos/consentimento de eventual voz usada.

## Canario neural real e avaliacao tecnica

Texto de comparacao:
"Olá! Eu sou o Ultron Voice. Agora falo diretamente no seu computador."

F4 Chatterbox PTBR:
- WAV E:\IA LOCAL\logs\ultron_voice\chatterbox_f4_20261122\chatterbox_ptbr_lab.wav
- Geracao completa 90,45s CPU.
- Audio 6,92s, 24000 Hz, mono, PCM16, 332204 bytes.
- Pico 0,94995, RMS 0,10768, nao silencioso.
- SHA256 3344fd60dffafef3dc283b3daac4213a0d013a9856efb696989a5594bb7ac95a
- Vosk PT ASR: "olá eu sou tão voz e agora fale diretamente no seu computador" (nome Ultron falhou); sem inferir qualidade artistica por ASR.
- Porta localhost:3900 VoiceStudio indisponivel no canario, sem dependencia ao runtime VoiceStudio.

F3 Qwen3 (referencia):
- WAV 7,92s, tempo geracao 92,35s CPU, 24000 Hz mono PCM16, SHA256 9f1e59f418eb12b5c8d2bea5928f8e716823387f6d65cbd47ee5d88baa6fe947
- Vosk tambem nao reconheceu corretamente "Ultron".
- Comparacao nao e cega/independente: Chatterbox foi condicionado no WAV Qwen com o mesmo texto. Nao declarar vencedor sem avaliacao humana e testes adicionais.

Envio privado: Hermes Telegram TESTE msg 2508; Qwen anterior msg 2487. NENHUMA postagens em canais.

## Protecoes e QA

- GameGuard verificado antes, durante e depois da sintese; falha bloqueia e destino antigo permanece intacto.
- Apenas CPU, ambiente sem tokens de API, cache HF offline, saida WAV atomica; worker com timeout 480s, controle por projeto.
- 55/55 testes focados PASS (F4, F3, F2, F1), compileall e diff-check PASS.
- Validado worker real, a geracao PCM, SHA256 e transcricao Vosk. Ainda precisa QA auditiva e benchmark GPU antes de comunicacao em tempo real.
- A entrega da PR nao significa producao; nao mergear as PRs empilhadas #2 -> #3 -> #4 -> F4 automaticamente.

## Proximo passo unico

Aguardar avaliacao auditiva do proprietario comparando as duas amostras privadas e corrigir pronunciacao/qualidade. Depois avaliar aceleracao segura (GameGuard, Intel Arc e GTX quando apropriado), sem competencia com jogo nem publicacao automatica.

Referencias:
https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br
https://huggingface.co/ResembleAI/chatterbox
https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br/tree/main
