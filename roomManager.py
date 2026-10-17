import threading

rooms = {}  # room_name -> set of usernames
lock = threading.Lock()

def join_room(room, username):
    with lock:
        if room not in rooms:
            rooms[room] = set()
        rooms[room].add(username)

def leave_room(room, username):
    with lock:
        if room in rooms:
            rooms[room].discard(username)
            if len(rooms[room]) == 0:
                del rooms[room]

def get_room_members(room):
    with lock:
        return list(rooms.get(room, []))

def remove_user_from_all(username):
    with lock:
        for r, members in list(rooms.items()):
            members.discard(username)
            if len(members) == 0:
                del rooms[r]
