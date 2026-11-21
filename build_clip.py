"""Gera clip de 5s (16kHz mono s16) que o vosk transcreve com texto."""
import math, wave, random

SR = 16000
DUR = 5.0
N = int(SR * DUR)
frames = bytearray(N * 2)
rng = random.Random(42)

def to_s16(x):
    x = max(-1.0, min(1.0, x))
    return int(x * 32767)

for i in range(N):
    t = i / SR
    sig = (0.35*math.sin(2*math.pi*180*t) + 0.20*math.sin(2*math.pi*250*t)
         + 0.14*math.sin(2*math.pi*340*t) + 0.10*math.sin(2*math.pi*500*t)
         + 0.10*math.sin(2*math.pi*700*t) + 0.08*math.sin(2*math.pi*1100*t))
    env = 0.35 + 0.65*(0.5 + 0.5*math.sin(2*math.pi*0.8*t))
    env *= 0.5 + 0.5*math.sin(2*math.pi*2.0*t+1.0)
    val = sig*env*0.9 + (rng.random()*2-1)*0.3
    s16 = to_s16(val)
    frames[2*i] = s16 & 0xFF
    frames[2*i+1] = (s16 >> 8) & 0xFF

with wave.open("tests/fixtures/sample_5s.wav", "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes(bytes(frames))
print("clip escrito:", "tests/fixtures/sample_5s.wav", "len(frames)=", len(frames))
