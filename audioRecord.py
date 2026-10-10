import pyaudio
import wave
import threading

is_recording = False
frames = []
p = None
stream = None

def start():
    global is_recording, frames, p, stream
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=2, rate=44100, input=True, frames_per_buffer=1024)
    frames = []
    is_recording = True
    
    def record_loop():
        while is_recording:
            try:
                frames.append(stream.read(1024, exception_on_overflow=False))
            except Exception:
                pass
                
    threading.Thread(target=record_loop, daemon=True).start()

def stop():
    global is_recording, stream, p, frames
    is_recording = False
    
    stream.stop_stream()
    stream.close()
    p.terminate()

    filename = "recordings/voice.wav"
    
    wt = wave.open(filename, "wb")
    wt.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wt.setnchannels(2)
    wt.setframerate(44100)
    wt.writeframes(b"".join(frames))
    wt.close()
    
    return filename

def play_wav(filepath):
    def _play():
        wf = wave.open(filepath, 'rb')
        p2 = pyaudio.PyAudio()
        s2 = p2.open(format=p2.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)
        data = wf.readframes(1024)
        while data:
            s2.write(data)
            data = wf.readframes(1024)
        s2.stop_stream()
        s2.close()
        p2.terminate()
    threading.Thread(target=_play, daemon=True).start()