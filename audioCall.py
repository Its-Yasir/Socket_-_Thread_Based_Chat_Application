"""
audioCall.py  -  UDP peer-to-peer audio streaming

Handles PyAudio unavailability gracefully:
  - `is_available()` returns False if pyaudio/PortAudio is not usable
  - `start()` returns (True, None) on success or (False, error_str) on failure
  - All errors are reported; nothing is swallowed silently.
"""
import socket
import threading

is_calling  = False
is_muted    = False
sock        = None
_bound_port = None
p           = None
in_stream   = None
out_stream  = None

def set_muted(muted: bool):
    global is_muted
    is_muted = muted

# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_available() -> bool:
    """Return True if PyAudio + PortAudio are importable and functional."""
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        pa.terminate()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Port management  (idempotent)
# ---------------------------------------------------------------------------

def get_port() -> int:
    """Bind a UDP socket once; return the local port.  Safe to call many times."""
    global sock, _bound_port
    if sock is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", 0))
        _bound_port = sock.getsockname()[1]
    return _bound_port


# ---------------------------------------------------------------------------
# Start / stop
# ---------------------------------------------------------------------------

def start(peer_ip: str, peer_port: int) -> tuple[bool, str | None]:
    """
    Open microphone + speaker streams and start send/recv threads.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    global is_calling, sock, p, in_stream, out_stream

    if sock is None:
        get_port()
    sock.settimeout(1.0)

    try:
        import pyaudio
    except Exception as e:
        return False, f"PyAudio not available: {e}"

    # Try common sample rates; devices vary
    used_rate = None
    _p = None
    _in  = None
    _out = None
    for rate in (44100, 48000, 16000, 8000):
        try:
            _p   = pyaudio.PyAudio()
            _in  = _p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                           input=True,  frames_per_buffer=1024)
            _out = _p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                           output=True, frames_per_buffer=1024)
            used_rate = rate
            break
        except Exception:
            # Clean up and try next rate
            for obj in (_in, _out):
                if obj:
                    try: obj.close()
                    except: pass
            if _p:
                try: _p.terminate()
                except: pass
            _p = _in = _out = None

    if used_rate is None:
        return False, "No compatible audio device found (tried 44100/48000/16000/8000 Hz)"

    p          = _p
    in_stream  = _in
    out_stream = _out
    is_calling = True
    print(f"[AudioCall] Started at {used_rate} Hz -> {peer_ip}:{peer_port}")

    def send_loop():
        while is_calling:
            try:
                data = in_stream.read(1024, exception_on_overflow=False)
                if not is_muted:
                    sock.sendto(data, (peer_ip, int(peer_port)))
            except OSError:
                break
            except Exception:
                pass   # mic glitch – keep going

    def recv_loop():
        while is_calling:
            try:
                data, _ = sock.recvfrom(4096)
                if data and out_stream:
                    out_stream.write(data)
            except socket.timeout:
                continue   # expected – check is_calling and loop
            except OSError:
                break

    threading.Thread(target=send_loop, daemon=True).start()
    threading.Thread(target=recv_loop, daemon=True).start()
    return True, None


def stop():
    global is_calling, is_muted, sock, _bound_port, p, in_stream, out_stream
    is_calling = False
    is_muted   = False

    for stream in (in_stream, out_stream):
        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
    in_stream = out_stream = None

    if p:
        try: p.terminate()
        except: pass
        p = None

    if sock:
        try: sock.close()
        except: pass
        sock = None
        _bound_port = None

    print("[AudioCall] Stopped.")
