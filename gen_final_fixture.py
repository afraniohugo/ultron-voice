from gtts import gTTS
import subprocess, pathlib, wave
FIX = pathlib.Path("tests/fixtures")
FIX.mkdir(exist_ok=True)
CAPTION = "cinco mais sete igual doze"
mp3 = FIX / "phrase.mp3"
gTTS(text=CAPTION, lang="pt", slow=False).save(str(mp3))
subprocess.run(["ffmpeg","-y","-v","error","-i",str(mp3),
                "-ar","16000","-ac","1","-sample_fmt","s16", str(FIX/"sample_5s.wav")], check=True)
mp3.unlink(missing_ok=True)
wf = wave.open(str(FIX/"sample_5s.wav"),"rb")
dur = wf.getnframes()/wf.getframerate()
print("fixture:", FIX/"sample_5s.wav", "duracao=%.1fs" % dur, "canal=%d" % wf.getnchannels())
wf.close()
