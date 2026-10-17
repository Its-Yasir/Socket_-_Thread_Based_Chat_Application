import clientRegistry
import roomManager

def handle_login(conn, parts):
    # LOGIN|username
    name = parts[1].strip() if len(parts) > 1 else ""
    if not name or "|" in name:
        conn.send("ERROR|Invalid username\n")
        return None
    if not clientRegistry.add_client(name, conn):
        conn.send("ERROR|Username already taken\n")
        return None
    
    conn.username = name
    conn.send("INFO|Logged in successfully\n")
    broadcast_users()
    return name

def broadcast_users():
    users = ",".join(clientRegistry.get_all_users())
    clientRegistry.broadcast(f"USERS|{users}\n")

def handle_msg(conn, parts):
    # MSG|room|text
    if len(parts) < 3:
        return
    room = parts[1].strip()
    text = "|".join(parts[2:])
    members = roomManager.get_room_members(room)
    print(f"[MSG] Room '{room}' from {conn.username} to {members}: {text}")
    for m in members:
        if m != conn.username:
            target_conn = clientRegistry.get_client(m)
            if target_conn:
                target_conn.send(f"MSG|{room}|{conn.username}|{text}\n")

def handle_pm(conn, parts):
    # PM|target_user|text
    if len(parts) < 3:
        return
    target_user = parts[1].strip()
    text = "|".join(parts[2:])
    target_conn = clientRegistry.get_client(target_user)
    print(f"[PM] From '{conn.username}' to '{target_user}' (Found: {target_conn is not None}): {text}")
    if target_conn:
        target_conn.send(f"PM|{conn.username}|{text}\n")
    else:
        conn.send(f"ERROR|User {target_user} is offline\n")

def handle_join(conn, parts):
    # JOIN|room
    if len(parts) < 2:
        return
    room = parts[1].strip()
    roomManager.join_room(room, conn.username)
    conn.send(f"INFO|Joined room {room}\n")

def handle_leave(conn, parts):
    # LEAVE|room
    if len(parts) < 2:
        return
    room = parts[1].strip()
    roomManager.leave_room(room, conn.username)
    conn.send(f"INFO|Left room {room}\n")

def handle_file(conn, cmd, parts):
    # FILESTART, FILECHUNK, FILEEND, FILEABORT: format: CMD|target|...
    if len(parts) < 2:
        return
    target = parts[1]
    # Replace target with sender
    forwarded = [cmd, conn.username] + parts[2:]
    line = "|".join(forwarded) + "\n"
    
    # Check if target is a group/room
    members = roomManager.get_room_members(target)
    if members:
        for m in members:
            if m != conn.username:
                target_conn = clientRegistry.get_client(m)
                if target_conn:
                    target_conn.send(line)
    else:
        # Private target
        target_conn = clientRegistry.get_client(target)
        if target_conn:
            target_conn.send(line)

import socket

def _resolve_ip(ip):
    if ip in ("127.0.0.1", "localhost", "::1"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            real_ip = s.getsockname()[0]
            s.close()
            return real_ip
        except Exception:
            pass
    return ip

def _get_call_ip(sender_conn, target_conn):
    sender_ip = sender_conn.addr[0]
    target_ip = target_conn.addr[0] if target_conn else ""
    # If both sender and target are on localhost (e.g. testing on same machine),
    # use 127.0.0.1 directly to avoid firewall or routing issues.
    if sender_ip in ("127.0.0.1", "localhost", "::1"):
        if target_ip in ("127.0.0.1", "localhost", "::1"):
            return "127.0.0.1"
        return _resolve_ip(sender_ip)
    return sender_ip

def handle_call(conn, parts):
    # CALL|target|mode|audioPort|videoPort
    if len(parts) < 5:
        return
    target = parts[1].strip()
    mode = parts[2].strip()
    aport = parts[3].strip()
    vport = parts[4].strip()
    target_conn = clientRegistry.get_client(target)
    client_ip = _get_call_ip(conn, target_conn)
    print(f"[CALL] From '{conn.username}' to '{target}' ({mode}) ip={client_ip} (Found: {target_conn is not None})")
    if target_conn:
        target_conn.send(f"INCOMING|{conn.username}|{mode}|{client_ip}|{aport}|{vport}\n")
    else:
        conn.send(f"ERROR|User {target} is offline\n")

def handle_accept(conn, parts):
    # ACCEPT|caller|audioPort|videoPort
    if len(parts) < 4:
        return
    caller = parts[1].strip()
    aport = parts[2].strip()
    vport = parts[3].strip()
    caller_conn = clientRegistry.get_client(caller)
    client_ip = _get_call_ip(conn, caller_conn)
    print(f"[ACCEPT] By '{conn.username}' for '{caller}' ip={client_ip} (Found: {caller_conn is not None})")
    if caller_conn:
        caller_conn.send(f"ACCEPTED|{conn.username}|{client_ip}|{aport}|{vport}\n")

def handle_reject(conn, parts):
    # REJECT|caller|reason
    caller = parts[1].strip() if len(parts) > 1 else ""
    reason = parts[2].strip() if len(parts) > 2 else "declined"
    caller_conn = clientRegistry.get_client(caller)
    print(f"[REJECT] By '{conn.username}' for '{caller}': {reason}")
    if caller_conn:
        caller_conn.send(f"REJECT|{conn.username}|{reason}\n")

def handle_endcall(conn, parts):
    # ENDCALL|other
    other = parts[1].strip() if len(parts) > 1 else ""
    other_conn = clientRegistry.get_client(other)
    print(f"[ENDCALL] By '{conn.username}' with '{other}'")
    if other_conn:
        other_conn.send(f"ENDCALL|{conn.username}\n")
