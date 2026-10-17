"""
videoCall.py  -  UDP peer-to-peer video streaming via OpenCV

Features:
- Dual-window display:
  * Large Receiving Window (640x480) for incoming peer video.
  * Small Sending Window (240x180) for local camera preview.
- Picture-in-Picture (PiP) toggle:
  * Press 'P' to embed self-view directly inside the corner of the large window.
  * Closing the small window automatically falls back to PiP mode.
- Mirror mode (press 'M' to toggle horizontal mirror flip on self-view).
- Hangup / Exit: Press 'Q' or ESC, or close the receiving window to end call.
- Styled placeholder screens when waiting for camera or network.
"""
import socket
import threading
import time

is_calling  = False
sock        = None
_bound_port = None
cap         = None

RECV_WIN = "Incoming Video (Receiving) - [Q: End Call | P: Toggle PiP]"
SEND_WIN = "My Camera (Sending) - [Small]"

RECV_WIDTH  = 640
RECV_HEIGHT = 480
SEND_WIDTH  = 240
SEND_HEIGHT = 180

PIP_WIDTH   = 160
PIP_HEIGHT  = 120

_latest_local_frame  = None
_latest_remote_frame = None
_frame_lock          = threading.Lock()
_pip_mode            = False
_mirror_mode         = True
_on_close_cb         = None


def is_available() -> bool:
    """Return True if cv2 is importable."""
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def set_on_close_callback(cb):
    """Register a callback invoked when the user closes the video window or presses Q."""
    global _on_close_cb
    _on_close_cb = cb


def get_port() -> int:
    global sock, _bound_port
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", 0))
        _bound_port = sock.getsockname()[1]
    return _bound_port


def start(peer_ip: str, peer_port: int) -> tuple[bool, str | None]:
    """
    Open webcam, start send, recv, and display threads.
    Returns (True, None) on success, (False, error_msg) on failure.
    """
    global is_calling, sock, cap
    global _latest_local_frame, _latest_remote_frame, _pip_mode

    try:
        import cv2
        import numpy as np
    except Exception as e:
        return False, f"OpenCV not available: {e}"

    if sock is None:
        get_port()
    sock.settimeout(1.0)

    _cap = None
    try:
        c = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if c.isOpened():
            _cap = c
        else:
            print("[VideoCall] Local camera unavailable; will receive video only.")
    except Exception as e:
        print(f"[VideoCall] Local camera open failed ({e}); will receive video only.")

    cap = _cap
    with _frame_lock:
        _latest_local_frame  = None
        _latest_remote_frame = None
    _pip_mode = False
    is_calling = True
    print(f"[VideoCall] Started -> {peer_ip}:{peer_port}")

    def send_loop():
        while is_calling and cap and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            with _frame_lock:
                global _latest_local_frame
                _latest_local_frame = frame.copy()

            # Compress for UDP transmission (fits well within single UDP datagram)
            small = cv2.resize(frame, (320, 240))
            _, encoded = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 40])
            data = encoded.tobytes()
            try:
                sock.sendto(data, (peer_ip, int(peer_port)))
            except OSError:
                break
            except Exception:
                pass

    def recv_loop():
        while is_calling and sock:
            try:
                data, _ = sock.recvfrom(65536)
                if not data:
                    continue
                arr = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    with _frame_lock:
                        global _latest_remote_frame
                        _latest_remote_frame = frame
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception:
                pass

    def display_loop():
        global is_calling, _pip_mode, _mirror_mode

        # Calculate centered screen coordinates so video windows sit cleanly at the top
        sw, sh = 1366, 768
        try:
            import ctypes
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            sh = ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            pass

        total_w = RECV_WIDTH + 16 + SEND_WIDTH
        start_x = max(20, (sw - total_w) // 2)
        cam_y = 20

        cv2.namedWindow(RECV_WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(RECV_WIN, RECV_WIDTH, RECV_HEIGHT)
        cv2.moveWindow(RECV_WIN, start_x, cam_y)

        send_win_active = False
        if not _pip_mode:
            cv2.namedWindow(SEND_WIN, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(SEND_WIN, SEND_WIDTH, SEND_HEIGHT)
            cv2.moveWindow(SEND_WIN, start_x + RECV_WIDTH + 16, cam_y)
            send_win_active = True

        try:
            while is_calling:
                # 1. Fetch latest frames
                with _frame_lock:
                    rem = _latest_remote_frame.copy() if _latest_remote_frame is not None else None
                    loc = _latest_local_frame.copy() if _latest_local_frame is not None else None

                # 2. Build Remote (Receiving) view - Large (640x480)
                if rem is not None:
                    disp_remote = cv2.resize(rem, (RECV_WIDTH, RECV_HEIGHT), interpolation=cv2.INTER_LINEAR)
                else:
                    disp_remote = np.zeros((RECV_HEIGHT, RECV_WIDTH, 3), dtype=np.uint8)
                    disp_remote[:] = (28, 28, 30)  # Dark background
                    cv2.putText(disp_remote, "Connecting video stream...", (140, 220),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (220, 220, 220), 2, cv2.LINE_AA)
                    cv2.putText(disp_remote, "Waiting for peer camera", (180, 260),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 140, 140), 1, cv2.LINE_AA)
                    cv2.putText(disp_remote, "[Press Q: End Call | P: PiP Mode]", (150, 440),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (110, 110, 110), 1, cv2.LINE_AA)

                # 3. Build Local (Sending) view - Small (240x180)
                if loc is not None:
                    local_view = cv2.flip(loc, 1) if _mirror_mode else loc
                    disp_local = cv2.resize(local_view, (SEND_WIDTH, SEND_HEIGHT), interpolation=cv2.INTER_LINEAR)
                    # Live indicator badge
                    cv2.circle(disp_local, (16, 16), 4, (0, 220, 0), -1)
                    cv2.putText(disp_local, "LIVE", (26, 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 0), 1, cv2.LINE_AA)
                    cv2.putText(disp_local, "You (Sending)", (14, SEND_HEIGHT - 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
                else:
                    disp_local = np.zeros((SEND_HEIGHT, SEND_WIDTH, 3), dtype=np.uint8)
                    disp_local[:] = (35, 35, 38)
                    status_text = "Opening camera..." if cap else "Camera Unavailable"
                    cv2.putText(disp_local, status_text, (20, SEND_HEIGHT // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

                # 4. Display according to mode
                if _pip_mode:
                    if send_win_active:
                        try: cv2.destroyWindow(SEND_WIN)
                        except Exception: pass
                        send_win_active = False

                    # Overlay in bottom-right corner of Receiving window
                    pip_img = cv2.resize(disp_local, (PIP_WIDTH, PIP_HEIGHT), interpolation=cv2.INTER_LINEAR)
                    x1 = RECV_WIDTH - PIP_WIDTH - 15
                    y1 = RECV_HEIGHT - PIP_HEIGHT - 15
                    x2 = x1 + PIP_WIDTH
                    y2 = y1 + PIP_HEIGHT

                    # Border & PiP frame
                    cv2.rectangle(disp_remote, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (255, 132, 10), 2)
                    disp_remote[y1:y2, x1:x2] = pip_img
                    # "You" badge
                    cv2.rectangle(disp_remote, (x1, y1), (x1 + 42, y1 + 18), (28, 28, 30), -1)
                    cv2.putText(disp_remote, "You", (x1 + 6, y1 + 13),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
                else:
                    if not send_win_active:
                        cv2.namedWindow(SEND_WIN, cv2.WINDOW_NORMAL)
                        cv2.resizeWindow(SEND_WIN, SEND_WIDTH, SEND_HEIGHT)
                        cv2.moveWindow(SEND_WIN, start_x + RECV_WIDTH + 16, cam_y)
                        send_win_active = True
                    cv2.imshow(SEND_WIN, disp_local)

                cv2.imshow(RECV_WIN, disp_remote)

                # 5. Process keyboard events
                key = cv2.waitKey(20) & 0xFF
                if key in (ord("q"), ord("Q"), 27):  # Q or ESC
                    break
                elif key in (ord("p"), ord("P")):
                    _pip_mode = not _pip_mode
                elif key in (ord("m"), ord("M")):
                    _mirror_mode = not _mirror_mode

                # 6. Check window close events (X button clicked)
                try:
                    p_recv = cv2.getWindowProperty(RECV_WIN, cv2.WND_PROP_VISIBLE)
                    if p_recv < 1:
                        break  # User closed receiving window -> end call
                    if send_win_active:
                        p_send = cv2.getWindowProperty(SEND_WIN, cv2.WND_PROP_VISIBLE)
                        if p_send < 1:
                            # User closed sending window -> smoothly switch to PiP
                            _pip_mode = True
                except Exception:
                    pass
        finally:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
            stop()
            if _on_close_cb:
                try:
                    _on_close_cb()
                except Exception:
                    pass

    threading.Thread(target=send_loop, daemon=True).start()
    threading.Thread(target=recv_loop, daemon=True).start()
    threading.Thread(target=display_loop, daemon=True).start()
    return True, None


def stop():
    global is_calling, sock, _bound_port, cap
    is_calling = False

    if cap:
        try: cap.release()
        except Exception: pass
        cap = None

    if sock:
        try: sock.close()
        except Exception: pass
        sock = None
        _bound_port = None

    try:
        import cv2
        cv2.destroyAllWindows()
    except Exception:
        pass

    print("[VideoCall] Stopped.")
