"""
callManager.py  -  Orchestrates audio/video call lifecycle

Errors from audioCall/videoCall are surfaced through a registered callback
so the GUI always sees them instead of them being silently swallowed.

Usage:
    callManager.set_callbacks(on_error=..., on_status_change=...)
"""
import threading
import audioCall
import videoCall

current_peer = None
current_mode = None
_current_client = None

# Callbacks registered by the GUI
_on_error         = None   # fn(str) – called with an error message
_on_status_change = None   # fn(bool, str) – called with (active, peer_name)

def _on_video_window_closed():
    print("[CallManager] Video window closed by user, ending call.")
    end_call()

if hasattr(videoCall, "set_on_close_callback"):
    videoCall.set_on_close_callback(_on_video_window_closed)


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def set_callbacks(on_error=None, on_status_change=None):
    global _on_error, _on_status_change
    _on_error         = on_error
    _on_status_change = on_status_change


def _report_error(msg: str):
    print(f"[CallManager] Error: {msg}")
    if _on_error:
        try:
            _on_error(msg)
        except Exception:
            pass


def _report_status(active: bool, peer: str = ""):
    print(f"[CallManager] Status: active={active} peer={peer!r}")
    if _on_status_change:
        try:
            _on_status_change(active, peer)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Initiate call  (HOST side)
# ---------------------------------------------------------------------------

def start_call(client, peer: str, mode: str):
    global current_peer, current_mode, _current_client
    _current_client = client
    current_peer = peer
    current_mode = mode

    a_port = audioCall.get_port()
    v_port = videoCall.get_port() if mode == "video" else 0
    client.send(f"CALL|{peer}|{mode}|{a_port}|{v_port}")
    print(f"[CallManager] Calling {peer} ({mode}) a={a_port} v={v_port}")


# ---------------------------------------------------------------------------
# Accept call  (CALLEE side)
# ---------------------------------------------------------------------------

def accept_call(client, caller: str, mode: str,
                caller_ip: str, caller_aport, caller_vport):
    global current_peer, current_mode, _current_client
    _current_client = client
    current_peer = caller
    current_mode = mode

    my_aport = audioCall.get_port()
    my_vport = videoCall.get_port() if mode == "video" else 0

    # Tell the caller our ports first, then start streaming
    client.send(f"ACCEPT|{caller}|{my_aport}|{my_vport}")
    print(f"[CallManager] Accepted call from {caller} ({mode})"
          f"  caller a={caller_aport} v={caller_vport}"
          f"  my    a={my_aport} v={my_vport}")

    def _start_streams():
        ok, err = audioCall.start(caller_ip, int(caller_aport))
        if not ok:
            _report_error(f"Audio stream failed: {err}")
            _cleanup()
            return

        if mode == "video" and int(caller_vport) != 0:
            ok2, err2 = videoCall.start(caller_ip, int(caller_vport))
            if not ok2:
                _report_error(f"Video stream failed: {err2}")
                # Audio still works – do NOT abort

        _report_status(True, caller)

    threading.Timer(0.3, _start_streams).start()


# ---------------------------------------------------------------------------
# Call accepted  (CALLER side – receives ACCEPTED from callee)
# ---------------------------------------------------------------------------

def handle_accepted(peer: str, peer_ip: str, peer_aport, peer_vport):
    print(f"[CallManager] ACCEPTED by {peer}  ip={peer_ip}"
          f"  a={peer_aport} v={peer_vport}")

    def _start_streams():
        ok, err = audioCall.start(peer_ip, int(peer_aport))
        if not ok:
            _report_error(f"Audio stream failed: {err}")
            _cleanup()
            return

        if current_mode == "video" and int(peer_vport) != 0:
            ok2, err2 = videoCall.start(peer_ip, int(peer_vport))
            if not ok2:
                _report_error(f"Video stream failed: {err2}")

        _report_status(True, peer)

    threading.Timer(0.1, _start_streams).start()


# ---------------------------------------------------------------------------
# End call
# ---------------------------------------------------------------------------

def end_call(client=None):
    global current_peer, _current_client
    c = client or _current_client
    if current_peer and c:
        try:
            c.send(f"ENDCALL|{current_peer}")
        except Exception:
            pass
    _cleanup()


def on_peer_ended():
    """Called when the remote side hangs up."""
    _cleanup()


def _cleanup():
    global current_peer, current_mode, _current_client
    audioCall.stop()
    videoCall.stop()
    _report_status(False, "")
    current_peer = None
    current_mode = None
    _current_client = None
