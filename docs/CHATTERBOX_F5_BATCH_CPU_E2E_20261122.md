# Ultron Voice F5 — Chatterbox PT-BR batch CPU, cold one-shot lab

Data: 22/11/2026 BRT | Host: OptimusPrime
Estagio: IMPLEMENTADO e TESTADO em worktree isolada (base PR #5).
Nao mesclado, nao implantado, nao habilitado no Hermes/MCP nem no Ultron Studio.

## Objetivo e alcance

O Chatterbox F4 iniciava um novo interpretador e recarregava todos os pesos
para cada capitulo em texto. Agora, para jobs audiobook somente-texto de 2 a 4
capitulos pequenos (<=280 caracteres cada e <=600 no total), o Ultron Voice
usa um unico worker local que carrega o modelo uma vez e gera os clips em
sequencia no mesmo processo. Para entradas mistas (arquivos+texto), maiores
ou diferentes, o fluxo anterior e preservado. Nao cria daemon nem modelo
persistentemente carregado.

## Garantias

- Usa os MESMOS modelos PT-BR da F4, licenca MIT e SHA256 fixos e revisados.
- A referencia de voz e o WAV SINTETICO do Qwen da F3, SHA256 fixo.
- Revalida licenca, manifest, pesos, SHA256 de codigo-fonte antes de iniciar o job.
- Worker no Python 3.11 isolado, PyTorch CPU. HF_HUB_OFFLINE=1,
  TRANSFORMERS_OFFLINE=1 e CUDA_VISIBLE_DEVICES vazio.
- Ambiente do worker filtrado de tokens e chaves; sem API paga/servidor/rede.
- Verifica GameGuard antes, durante (poll a cada 3 s) e depois do processo.
- Saidas temporarias WAV PCM sao validadas em conjunto; se falhar, nao move
  os clips ao destino. A concatenacao final do audiobook usa arquivo atomico
  e checksum SHA256, como na F1.
- O lote de WAV individuais nao e uma transacao de filesystem: uma falha
  rara de escrita entre renames poderia deixar parte dos clips. No caminho
  audiobook os clips sao internos a pasta temporaria e o resultado final
  so e publicado apos todos eles passarem.
- Nenhum arquivo real de pessoa, clonagem humana ou sintese comercial.
- Comparacao de qualidade humana A/B Qwen vs Chatterbox F4 continua pendente.

## Comprovacao E2E em CPU (F5)

Entrada: 2 capitulos, "Olá! Eu sou o Ultron Voice." e
"Estou pronto para ajudar você em português.".

- Saida WAV (audio concatenado):
  E:\IA LOCAL\logs\ultron_voice\chatterbox_f5_20261122\chatterbox_ptbr_batch2.wav
- Duracao do audio: 10,60 s; mono PCM 16 bits, 24000 Hz.
- Tamanho: 508844 bytes.
- Geracao total (load + 2 sinteses + concatenacao): 119,32 s.
- SHA256: 3322d991b4ce9539c41bb912fa7e92806359314a7e30561eb5aa4756ec9859d0.
- Nao silencioso: RMS 0,072983, pico 0,517242.
- Vosk local PT: "olá eu sou um tom voz estou pronto para ajudar você em português".
  Marca "Ultron" ainda nao foi reconhecida corretamente.
- Log de execucao:
  E:\IA LOCAL\logs\ultron_voice\chatterbox_f5_20261122\run.stdout.log
- Sem inferencia de GPU ou VoiceStudio.

Nao fazer claim quantitativo de aceleracao vs F4:
F4 foi outra frase, com 6,92 s de audio e 90,45 s de geracao. Para
benchmark justo sera preciso medir os mesmos textos isoladamente
e comparar latencia fria/quente em condicoes semelhantes.
O F5 prova SOMENTE que um batch de 2 trechos funciona com 1 load,
reduzindo a necessidade estrutural de recargas repetidas.

## QA

- pytest foco F5 + F4/F3/F2/F1: 69/69 PASS (nenhuma falha).
- compileall PASS, git diff --check PASS.
- Wheel offline PASS e inclui chatterbox_batch.py, chatterbox_batch_worker.py.
- Canario real audio WAV e Vosk ASR PASS.
- Nao ha E2E real com Ultron Studio, MCP, conversacao ao vivo ou clonagem.

## Proximo passo unico

Com as amostras privadas Qwen #2487 e Chatterbox #2508, obter avaliacao
auditiva do dono e realizar benchmark controlado da aceleracao (eventual
Intel Arc sem interferir com jogos ou GPU reservada). Nao fazer deploy,
merge nem publicar canal sem gates de seguranca e qualidade.
