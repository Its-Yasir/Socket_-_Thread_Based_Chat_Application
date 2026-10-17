import base64
import os

# tid -> file_handle  (open for writing)
incoming_files = {}
incoming_file_paths = {}

def handle_file_start(sender, tid, filename, size, client):
    """Begin receiving a file transfer."""
    os.makedirs("downloads", exist_ok=True)
    # Sanitise filename: strip path separators to prevent directory traversal
    safe_name = os.path.basename(filename).replace("..", "")
    if not safe_name:
        safe_name = "received_file"

    # Avoid clobbering existing files if duplicate name
    base, ext = os.path.splitext(safe_name)
    filepath = f"downloads/{safe_name}"
    counter = 1
    while os.path.exists(filepath):
        filepath = f"downloads/{base}_{counter}{ext}"
        counter += 1

    # If a previous transfer with this tid is still open, close it first
    if tid in incoming_files:
        try:
            incoming_files[tid].close()
        except Exception:
            pass
    try:
        incoming_files[tid] = open(filepath, "wb")
        incoming_file_paths[tid] = filepath
    except Exception as e:
        print(f"[FileReceive] Cannot open {filepath}: {e}")

def handle_file_chunk(sender, tid, b64_data, client):
    """Write a decoded chunk to the in-progress file."""
    if tid not in incoming_files:
        return
    try:
        incoming_files[tid].write(base64.b64decode(b64_data))
    except Exception as e:
        print(f"[FileReceive] Chunk error for {tid}: {e}")

def handle_file_end(sender, tid, client):
    """Finalise the received file and notify the GUI."""
    if tid not in incoming_files:
        return
    f = incoming_files.pop(tid)
    filepath = incoming_file_paths.pop(tid, f"downloads/{tid}")
    try:
        f.close()
    except Exception:
        pass
    client.q.put(f"@FILERECEIVED|{sender}|{tid}|{filepath}")
