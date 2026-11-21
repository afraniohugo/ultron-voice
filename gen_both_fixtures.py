from gtts import gTTS
import subprocess, pathlib, wave
FIX = pathlib.Path("tests/fixtures"); FIX.mkdir(exist_ok=True)
CAPTION_PT = "cinco mais sete igual doze"
CAPTION_EN = "one plus one equals two"
for cap, out in ((CAPTION_PT, FIX/"sample_5s.wav"), (CAPTION_EN, FIX/"sample_5s_en.wav")):
    mp3 = FIX / (out.stem + ".mp3")
    gTTS(text=cap, lang="pt" if out is FIX/"sample_5s.wav" else "en", slow=False).save(str(mp3))
    subprocess.run(["ffmpeg","-y","-v","error","-i",str(mp3),"-ar","16000","-ac","1","-sample_fmt","s16",str(out)], check=True)
    mp3.unlink(missing_ok=True)
    wf = wave.open(str(out),"rb")
    print("fixture", out.name, "duracao=%.1fs" % (wf.getnframes()/wf.getframerate()))
    wf.close()
