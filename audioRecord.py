import os
import wave
import threading
import pyaudio

is_recording = False
frames = []
p = None
stream = None
current_rate = 16000
lock = threading.Lock()

def _audio_callback(in_data, frame_count, time_info, status):
    if is_recording and in_data:
        frames.append(in_data)
    return (None, pyaudio.paContinue)

def start():
    global is_recording, frames, p, stream, current_rate
    with lock:
        if is_recording:
            return True
        frames = []
        is_recording = True

        try:
            p = pyaudio.PyAudio()
            # Try standard rates: 16000 first, fallback to 44100 / 48000
            for rate in (16000, 44100, 48000):
                try:
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=rate,
                        input=True,
                        frames_per_buffer=1024,
                        stream_callback=_audio_callback
                    )
                    current_rate = rate
                    stream.start_stream()
                    return True
                except Exception:
                    continue

            print("[Audio Record] No supported input rate found")
            is_recording = False
            if p:
                p.terminate()
                p = None
            return False
        except Exception as e:
            print(f"[Audio Record Error] {e}")
            is_recording = False
            return False

def stop():
    global is_recording, stream, p, frames, current_rate
    with lock:
        if not is_recording and not stream:
            return "recordings/voice.wav" if os.path.exists("recordings/voice.wav") else None
        is_recording = False

        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            stream = None

        if p:
            try:
                p.terminate()
            except Exception:
                pass
            p = None

        os.makedirs("recordings", exist_ok=True)
        import time
        filename = f"recordings/voice_{time.strftime('%Y%m%d_%H%M%S')}.wav"

        try:
            wt = wave.open(filename, "wb")
            wt.setsampwidth(2)
            wt.setnchannels(1)
            wt.setframerate(current_rate)
            wt.writeframes(b"".join(frames))
            wt.close()
            return filename
        except Exception as e:
            print(f"[Wave Save Error] {e}")
            return None

def play_wav(filepath):
    if not filepath or not os.path.exists(filepath):
        return
    def _play():
        try:
            wf = wave.open(filepath, 'rb')
            p2 = pyaudio.PyAudio()
            s2 = p2.open(
                format=p2.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            data = wf.readframes(1024)
            while data:
                s2.write(data)
                data = wf.readframes(1024)
            s2.stop_stream()
            s2.close()
            p2.terminate()
        except Exception as e:
            print(f"[Audio Play Error] {e}")
    threading.Thread(target=_play, daemon=True).start()