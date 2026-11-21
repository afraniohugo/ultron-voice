#!/bin/sh
cd "/e/IA LOCAL/GitHub/ultron-voice/tests/fixtures"
ffmpeg -y -v error -i gttts_pt.mp3 -ar 16000 -ac 1 -sample_fmt s16 gttts_pt.wav
echo "wav: gttts_pt.wav"
