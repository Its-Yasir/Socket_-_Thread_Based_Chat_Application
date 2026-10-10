import cv2
import threading
import time

is_recording = False
cap = None
out = None

def start():
    global is_recording, cap, out
    cap = cv2.VideoCapture(0)
    
    filename = "recordings/output_video.avi"
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))
    is_recording = True

    def record_loop():
        global is_recording, cap, out
        while is_recording and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
            time.sleep(1/20.0) # Approx 20 FPS

    threading.Thread(target=record_loop, daemon=True).start()

def stop():
    global is_recording, cap, out
    is_recording = False
    time.sleep(0.1) # Let the recording loop finish the last frame
    
    if cap:
        cap.release()
    if out:
        out.release()
    
    return "recordings/output_video.avi"

def play_video(filepath):
    def _play():
        p_cap = cv2.VideoCapture(filepath)
        while p_cap.isOpened():
            ret, frame = p_cap.read()
            if not ret:
                break
            cv2.imshow('Playback (Press q to close)', frame)
            if cv2.waitKey(50) & 0xFF == ord('q'):
                break
        p_cap.release()
        try:
            cv2.destroyWindow('Playback (Press q to close)')
        except Exception:
            pass
            
    threading.Thread(target=_play, daemon=True).start()