import socket
import threading

class Connection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.username = None
        self._lock = threading.Lock()
        self.reader = sock.makefile("r", encoding="utf-8")

    def send(self, line):
        if not line.endswith("\n"):
            line += "\n"
        data = line.encode("utf-8")
        with self._lock:
            try:
                self.sock.sendall(data)
            except Exception:
                pass

    def readline(self):
        try:
            return self.reader.readline()
        except Exception:
            return ""

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
