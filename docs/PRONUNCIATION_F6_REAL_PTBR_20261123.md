# AFRANTECH Ultron Voice F6 — Ensaio de pronúncia "Ultron" (PT-BR)

Host OptimusPrime | Data local 22-23/11/2026 | Etapa LAB E2E testada, nao implantada
Base: F5 PR #6 -> F4 #5 -> F3 #4 -> F2 #3 -> F1 #2.

## Objetivo e limites

O ASR Vosk PT da F3-F5 nao reconheceu consistentemente "Ultron".
A F6 testa 3 realizacoes textuais com MESMO contexto Chatterbox PTBR MIT e
referencia sintetica Qwen F3, sem alterar a grafia canonica nem fazer
correcao automatica em producao:
1. Ultron (original)
2. Últron (acento na primeira silaba)
3. Ultrôn (acento na ultima silaba)

Apenas um token exato "Ultron" permitido na frase. Limite 170 chars, sem
controles. Motor batch local uma carga do modelo, manifestos/pesos/codigo
pinned hashes, HF offline, CUDA_VISIBLE_DEVICES vazio, GameGuard
pre/durante/depois. Sem clonagem humana ou publicacao. As fontes ficam em
branch isolada F6, os arquivos de audio em pasta de teste exclusiva.

## Ensaio real

Texto: "Olá! Eu sou o Ultron. Estou pronto para ajudar."

| Variante | Segundos | SHA256 da WAV |
| --- | ---: | --- |
| Original: Ultron | 7,24 | 02d7195dca6b9077df8e09226cf3b4232f7bf9d7441baa50e53953877345e809 |
| Primeira silaba: Últron | 6,80 | 14e1f8cb756174ba77aebe470ea29a27761b653c1fea5092125063e186797735 |
| Ultima silaba: Ultrôn | 6,88 | 94dc61902a1e4c88521ea55ab2ce6d06d653324106de071e7faeab82026940a9 |

Comparacao junta as tres, com pausas de 600ms:
E:\IA LOCAL\logs\ultron_voice\pronunciation_f6_20261122\comparison_ultron_3_variants.wav
SHA256 = 4b41b367df6b5c621254088f2f2ffa07930a9759e52addd1eb528180ff7bc3a0
Tamanho = 1.061.804 bytes, WAV PCM 24 kHz mono 16-bit.
Tempo total F6 CPU = 188,2 segundos. Arquivos/recibo SHA256:
E:\IA LOCAL\logs\ultron_voice\pronunciation_f6_20261122\pronunciation_lab_receipt.json
Enviado ao Telegram PRIVADO, legenda TESTE, sem publicar em canais.

## ASR da pronuncia individual — nenhuma aprovada

Vosk PT small, WAV reamostrados para 16k:
- Ultron: "olá eu sou um tom estou pronto para ajudar"
- Últron: "olá eu sou e estou pronto para ajudar"
- Ultrôn: "olá eu sou trono estou pronto para ajudar"

Nao conseguiu reconhecer Ultron corretamente em nenhuma. O ASR nao
mede qualidade artistica. Nenhuma correcao aplicada ao default. Necessaria
homologacao auditiva.

## Benchmark de latencia da F5 — INVALIDADO

Foi tentada comparacao entre duas geracoes individuais com as mesmas duas
frases do batch F5. Duas copias do script benchmark_single_f6.ps1
executaram ao mesmo tempo, competindo por CPU e escrevendo nos mesmos
arquivos; foram vistos tempos inconsistentes single_1 84,94s no stdout
e 77,06s no recibo, mais escrita apos recibo final. Todos resultados desse
benchmark sao INVALIDOS para estimar aceleracao da F5. Os processos
deste proprio experimento PIDs 40068 e 41780 e seus descendentes foram
encerrados, sem deixar trabalhos desse benchmark ativos.
Logs originais preservados; laudo:
E:\IA LOCAL\logs\ultron_voice\benchmark_f6_20261123\invalidated_comparison.json

A proxima medicao deve usar lock interprocesso unico, caminho unico por
tentativa, textos identicos, mesmo estado de jogo e ausencia de outros
inferidores; nunca alegar speedup a partir da medicao invalida.

## Qualidade/operacao

- QA de codigo: pytest F6 + F5/F4/F3/F2/F1.
- Build offline e compileall com arquivos F6 incluidos.
- Nada de VoiceStudio, GPU, merge, deploy, cron, reboot ou API paga.
- Proximo passo unico: audicao humana e eventual normalizacao aprovada
  do nome; criar benchmark exclusivo por lock, repetir medidas,
  depois pesquisar aceleracao local segura para dialogo ao vivo.
