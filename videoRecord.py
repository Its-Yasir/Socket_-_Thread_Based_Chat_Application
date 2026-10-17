import cv2
import threading
import os
import time

is_recording = False
cap = None
out = None
_filepath = None

def start():
    global is_recording, cap, out, _filepath
    if is_recording:
        return   # already recording
    is_recording = True
    _filepath = None

    def record_loop():
        global is_recording, cap, out, _filepath
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                print("[Video Record] Could not open camera.")
                is_recording = False
                return
            os.makedirs("recordings", exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"recordings/video_{ts}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))
            _filepath = filename
            while is_recording and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
                time.sleep(1 / 20.0)
        except Exception as e:
            print(f"[Video Record Error] {e}")
        finally:
            is_recording = False

    threading.Thread(target=record_loop, daemon=True).start()

def stop():
    global is_recording, cap, out
    is_recording = False
    time.sleep(0.15)   # Let the recording loop finish its last frame

    if cap:
        try:
            cap.release()
        except Exception:
            pass
        cap = None

    if out:
        try:
            out.release()
        except Exception:
            pass
        out = None

    # Only return the path if the file actually exists and has content
    if _filepath and os.path.exists(_filepath) and os.path.getsize(_filepath) > 0:
        return _filepath
    return None

def play_video(filepath):
    if not filepath or not os.path.exists(filepath):
        return

    def _play():
        p_cap = cv2.VideoCapture(filepath)
        while p_cap.isOpened():
            ret, frame = p_cap.read()
            if not ret:
                break
            cv2.imshow("Playback (Press q to close)", frame)
            if cv2.waitKey(50) & 0xFF == ord("q"):
                break
        p_cap.release()
        try:
            cv2.destroyWindow("Playback (Press q to close)")
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()