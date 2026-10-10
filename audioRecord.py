import pyaudio
import wave
from array import array
from struct import pack


def record(file):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    RATE = 44100
    r_Time=10
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print(" Recording Started...!!")
    frames=[]
    for i in range (0, int(RATE/CHUNK * r_Time)):
        data= stream.read(CHUNK)
        frames.append(data)

    print(" Recording ended...!!")
    stream.stop_stream()
    stream.close()
    p.terminate()

    wt=wave.open(file, "wb")
    wt.setsampwidth(p.get_sample_size(FORMAT))
    wt.setnchannels(CHANNELS)
    wt.setframerate(RATE)
    wt.writeframes(b"".join(frames))
    wt.close()

record("recording.wav")