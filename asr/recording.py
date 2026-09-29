# pip install sounddevice numpy
import sounddevice as sd
import numpy as np

print("Говори 5 секунд...")
audio = sd.rec(
    int(5 * 16000),
    samplerate=16000,
    channels=1,
    dtype='int16'
)
sd.wait()

with open("test_audio.pcm", "wb") as f:
    f.write(audio.tobytes())

print("Сохранено в test_audio.pcm")