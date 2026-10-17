import socket
import threading
from protocol import Connection
import clientRegistry
import roomManager
import serverHandlers

HOST = "0.0.0.0"
PORT = 5000

def handle_client(sock, addr):
    conn = Connection(sock, addr)
    username = None
    try:
        while True:
            line = conn.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            parts = line.split("|")
            cmd = parts[0]

            if cmd == "LOGIN":
                username = serverHandlers.handle_login(conn, parts)
            elif not username:
                conn.send("ERROR|Must login first\n")
            elif cmd == "MSG":
                serverHandlers.handle_msg(conn, parts)
            elif cmd == "PM":
                serverHandlers.handle_pm(conn, parts)
            elif cmd == "JOIN":
                serverHandlers.handle_join(conn, parts)
            elif cmd == "LEAVE":
                serverHandlers.handle_leave(conn, parts)
            elif cmd in ["FILESTART", "FILECHUNK", "FILEEND", "FILEABORT"]:
                serverHandlers.handle_file(conn, cmd, parts)
            elif cmd == "CALL":
                serverHandlers.handle_call(conn, parts)
            elif cmd == "ACCEPT":
                serverHandlers.handle_accept(conn, parts)
            elif cmd == "REJECT":
                serverHandlers.handle_reject(conn, parts)
            elif cmd == "ENDCALL":
                serverHandlers.handle_endcall(conn, parts)
    except Exception as e:
        print(f"[Error] Client {addr}: {e}")
    finally:
        if username:
            clientRegistry.remove_client(username)
            roomManager.remove_user_from_all(username)
            serverHandlers.broadcast_users()
        conn.close()
        print(f"[Disconnected] {addr} ({username})")

def start_server(host=HOST, port=PORT):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(10)
    print(f"Chat Server running on {host}:{port}")

    try:
        while True:
            sock, addr = server_sock.accept()
            print(f"[Connected] {addr}")
            threading.Thread(target=handle_client, args=(sock, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server_sock.close()

if __name__ == "__main__":
    start_server()
