import os
import base64
import threading

incoming_files = {}

def send_file_thread(client, target, filepath):
    filename = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    tid = filename  # Use filename as a simple ID
    
    client.send(f"FILESTART|{target}|{tid}|{filename}|{size}")
    
    f = open(filepath, "rb")
    while True:
        chunk = f.read(32768)
        if not chunk:
            break
        client.send(f"FILECHUNK|{target}|{tid}|{base64.b64encode(chunk).decode()}")
    f.close()
            
    client.send(f"FILEEND|{target}|{tid}")
    client.q.put(f"@FILESENT|{tid}|{filename}")

def send_file(client, target, filepath):
    threading.Thread(target=send_file_thread, args=(client, target, filepath), daemon=True).start()

def handle_file_start(sender, tid, filename, size, client):
    # Just store the open file handle directly
    incoming_files[tid] = open(f"downloads/{filename}", "wb")

def handle_file_chunk(sender, tid, b64_data, client):
    # Decode and write straight to the file
    incoming_files[tid].write(base64.b64decode(b64_data))

def handle_file_end(sender, tid, client):
    # Close it and tell the GUI
    f = incoming_files.pop(tid)
    f.close()
    client.q.put(f"INFO|Received file from {sender} successfully!")