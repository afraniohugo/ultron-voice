"""Gera clip 'fala-roboto' de 5s com amplitude real, para o vosk retornar texto nao-vazio."""
import math, wave, random

SR = 16000
DUR = 5.0
N = int(SR * DUR)
frames = bytearray(N * 2)
rng = random.Random(7)

def to_s16(x):
    x = max(-1.0, min(1.0, x))
    return int(x * 32767)

def formant(t, freqs, amp=0.7):
    out = 0.0
    for k, f in enumerate(freqs):
        out += 0.6 * math.sin(2*math.pi*f*t + k*1.3)
    return out * amp

for idx in range(16):
    base = int((idx * 0.30 + (idx * 0.05)) * SR)   # posicao do inicio da silaba
    if base >= N:
        break
    n = int(SR * 0.26)                              # ~0.26s silaba
    pitch = 180.0 + 25.0 * math.sin(2*math.pi*0.6*idx)
    for i in range(n):
        t = i / SR
        f1 = 380.0 + 320.0*math.sin(2*math.pi*1.2*t + idx)
        f2 = 1450.0 + 560.0*math.sin(2*math.pi*1.2*t + idx + 1.0)
        f3 = 2500.0 + 700.0*math.sin(2*math.pi*1.2*t + idx + 2.0)
        env = 0.7 * (0.5 + 0.5*math.sin(2*math.pi*9*t))
        sig = formant(t, [f1, f2, f3]) * env + pitch*0.0008
        s16 = to_s16(0.8 * sig)
        j = base + i
        if j < N:
            frames[2*j] = s16 & 0xFF
            frames[2*j+1] = (s16 >> 8) & 0xFF
    # paralize de baixo nivel entre silabas (ruido por 0.07s)
    k0 = base + n
    k1 = min(int((idx*0.30+0.0)*SR) + int((idx+1)*0.30)*SR, N)
    k0 = int((idx*0.30 + 0.26)*SR)
    k1 = int((idx*0.30 + 0.30)*SR)
    for j in range(k0, min(k1, N)):
        v = int((rng.random()*2-1)*2500)
        frames[2*j] = v & 0xFF
        frames[2*j+1] = (v >> 8) & 0xFF

with wave.open("tests/fixtures/sample_5s.wav", "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes(bytes(frames))
print("clip gerado:", "tests/fixtures/sample_5s.wav", len(frames))
