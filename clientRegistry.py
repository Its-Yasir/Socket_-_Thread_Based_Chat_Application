import threading

clients = {}  # username -> sock_or_conn
lock = threading.Lock()

def add_client(username, conn):
    with lock:
        if username in clients:
            return False
        clients[username] = conn
        return True

def remove_client(username):
    with lock:
        if username in clients:
            del clients[username]

def get_client(username):
    with lock:
        return clients.get(username)

def get_all_users():
    with lock:
        return list(clients.keys())

def broadcast(line, sender=None):
    with lock:
        snapshot = list(clients.items())
    for name, conn in snapshot:
        if name != sender:
            try:
                conn.send(line)
            except Exception:
                pass
