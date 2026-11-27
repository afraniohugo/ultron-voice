# Captura e proteção de eco — laboratório 26/11/2026

Status: candidato; não ativar automaticamente ou promover em produção.

- `audio_turns.py`: lease half-duplex por processo, consentimento explícito, GameGuard e intervalo de 350 ms após playback. A integração dos demais players com o lease é obrigatória para proteção efetiva. Não é AEC nem mutex global.
- `capture_lab.py`: FFmpeg DirectShow, dispositivo explicitamente selecionado, consentimento, captura de 1 a 30 segundos, PCM16 mono 16 kHz em memória, prazo e cancelamento do processo próprio. Não registrado em MCP/GUI; nenhuma captura física realizada. Dispositivos com nomes duplicados não foram homologados.
- `tests/test_audio_turns_capture.py`: 6/6 testes; filhos Python inertes fornecem PCM sintético ou simulam espera. Não testam drivers ou hardware.

## Ensaio DSP separado

FFmpeg instalado possui filtro anlms. Referência de ruído pseudoaleatório seed 20261126, 4 s, 16 kHz, amplitude RMS 0,12; eco = 0,55 da referência atrasada 64 amostras + 0,20 atrasada 91 amostras. Sinal independente near-end RMS 0,08 na segunda metade.

Filtro: `[0:a][1:a]anlms=order=128:mu=0.1:eps=0.001:out_mode=o[out]`, entradas referência e microfone sintético respectivamente. Saída float32. Métricas calculadas sobre últimos 2 s.

| Modo | Redução eco isolado (dB) | SNR antes (dB) | SNR depois (dB) | Correlação near-end | Resultado |
|---|---:|---:|---:|---:|---|
| e | 0.00 | 1.19 | -2.58 | -0.0066 | FAIL |
| n | -5.94 | 1.19 | -6.01 | 0.0070 | FAIL |
| o | 106.14 | 1.19 | 12.75 | 0.9745 | PASS |

Critérios originais: redução eco isolado >15 dB, ganho SNR >6 dB, correlação >0,85. O resultado extremo de eco isolado representa um caminho de eco artificial fixo e linear, não desempenho acústico real.

Recibos em `E:\IA LOCAL\lab\ultron-voice-recovery-20261125\echo-reference-nlms-20261126`:
- receipt.json (modo e, falha), SHA256 075d7ed693b7d16a5426fc9625a98931f880e556cb6c3b359532b6855f09f529
- output-mode-diagnosis.json (modos o/n, mesmos sinais), SHA256 0fb521e41d030169743d48b62cebddf5296ae78e67f0dce79370601267116c5a
- reference.f32, echo.f32, near.f32, mixed.f32 e saídas preservadas.

Ainda necessário: integrar captura/playback de forma consentida na GUI, referência de reprodução sincronizada, atraso variável, deriva dos relógios, double-talk real, ruído, clipping, dispositivos e segurança/teardown. Não ativar AEC experimental em produção. Preferir half-duplex até aceite físico independente. Sem novos serviços, dependências instaladas ou chamadas pagas.
