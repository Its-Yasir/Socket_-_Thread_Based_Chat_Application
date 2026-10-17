import os
import base64
import threading
import time

def send_file_thread(client, target, filepath):
    try:
        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        tid = filename  # Use filename as ID
        
        client.send(f"FILESTART|{target}|{tid}|{filename}|{size}")
        time.sleep(0.02)
        
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(16384)  # 16 KB chunks
                if not chunk:
                    break
                b64 = base64.b64encode(chunk).decode("ascii")
                client.send(f"FILECHUNK|{target}|{tid}|{b64}")
                time.sleep(0.01)  # 10ms pacing prevents socket buffer saturation
                
        time.sleep(0.02)
        client.send(f"FILEEND|{target}|{tid}")
        client.q.put(f"@FILESENT|{target}|{filename}|{filepath}")
    except Exception as e:
        client.q.put(f"@FILEFAILED|{filepath}|{e}")

def send_file(client, target, filepath):
    threading.Thread(target=send_file_thread, args=(client, target, filepath), daemon=True).start()