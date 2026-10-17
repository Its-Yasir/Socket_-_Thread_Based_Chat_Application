# Project Documentation, Report & Presentation Master Plan

This project is made by Saim

This document provides a comprehensive, step-by-step master plan to prepare the **Final Project Report** and the **Final Project Presentation/Demo** for the **Real-Time Multi-User Socket- and Thread-Based Chat Application**.

It details exact guidelines on:

- **Files, Their Use, and Internal Workings**: Complete technical breakdown of every single file in the project.
- **Libraries and Their Roles**: Detailed analysis of standard and external dependencies.
- **Important Functions, Parameters, and Return Types**: Complete signatures and operational explanations for all core functions.
- **Working GUI Screenshots**: Where and how to capture/insert 17 working GUI screenshots.
- **System Architecture Diagrams & Visual Flowcharts**: Placement and contents of architectural visuals.
- **Presentation & Live Demo Script**: Exact script and viva defense cheat sheet for examiners.

_(Note: All source code screenshots have been excluded in favor of actual working GUI screenshots, architectural diagrams, and comprehensive technical depth)._

---

## Part 1: Project Overview & Rubric Alignment

### 1.1 Project Summary

A multi-threaded client-server communication suite developed using standard Python network libraries (`socket`, `threading`, `queue`) and modular multimedia utilities (`pyaudio`, `opencv-python`). It features:

- **TCP Stream Framing**: Guaranteed reliability for text messaging, channel rooms, file transmissions, and call signaling.
- **Direct UDP Peer-to-Peer Streaming**: High-throughput, low-latency live audio and video streaming directly between clients.
- **Strict Separation of Concerns**: Monolithic styling and UI thread confinement in `gui.py`, with decoupled, purely procedural functional modules.

### 1.2 Evaluation Mapping

| Feature / Requirement                    | Module / Implementation                                                                   | Marks Target |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- | ------------ |
| **Core Client-Server Communication**     | `server.py`, `protocol.py`, `config.py`                                                   | 4 Marks      |
| **Group & Private Chatting**             | `roomManager.py`, `clientRegistry.py`, `serverHandlers.py`, `gui.py`                      | 3 Marks      |
| **File & Media Transfers**               | `fileTransfer.py`, `fileReceive.py`, `audioRecord.py`, `videoRecord.py`                   | 2 Marks      |
| **Multi-threading & Network Efficiency** | Worker threads, locks, UDP audio/video (`audioCall.py`, `videoCall.py`, `callManager.py`) | 3 Marks      |
| **Structure & Documentation**            | Modular flat files, report, diagrams, presentation                                        | 2 Marks      |
| **User Interface (GUI)**                 | Dark-themed, responsive Tkinter desktop client (`gui.py`)                                 | 1 Mark       |

---

## Part 2: Complete Inventory of Files, Libraries & Core Functions

### 2.1 File Catalog: Workings & Responsibilities

| #   | File Name           | Role / Side              | Detailed Workings & Responsibilities                                                                                                                                                                                 |
| --- | ------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `config.py`         | Shared (Server & Client) | Central repository of configuration constants (server IP, port `5000`, 32 KB chunk size, 50 MB max file size, connection timeouts). Prevents magic numbers.                                                          |
| 2   | `protocol.py`       | Shared (Server & Client) | Implements the `Connection` class. Manages newline framing (`\n`), thread-safe socket writing via `threading.Lock`, and clean shutdown with `socket.SHUT_RDWR`.                                                      |
| 3   | `clientRegistry.py` | Server Side              | Thread-safe user registry (`username -> Connection`). Protects user state with a mutex lock and takes snapshot copies of active connections to prevent deadlocks during broadcasts.                                  |
| 4   | `roomManager.py`    | Server Side              | Thread-safe group chat directory (`room_name -> set(usernames)`). Handles creation, joining, leaving, empty room deletion, and automatic multi-room purging on disconnect.                                           |
| 5   | `serverHandlers.py` | Server Side              | Command processing engine. Sanitizes inputs, validates room memberships, routes private messages, forwards Base64 file chunks statelessly, and brokers call signaling.                                               |
| 6   | `server.py`         | Server Side              | Central daemon process. Binds to `0.0.0.0:5000` with `SO_REUSEADDR`, runs the infinite accept loop, spawns per-client worker daemon threads, and guarantees disconnect cleanup via `try/finally`.                    |
| 7   | `fileTransfer.py`   | Client Side              | Non-blocking file transmitter. Runs on a daemon thread, reads files in 32 KB binary chunks, Base64-encodes them, streams `FILESTART`/`FILECHUNK`/`FILEEND` over TCP, and reports progress to `client.q`.             |
| 8   | `fileReceive.py`    | Client Side              | File reassembly handler. Listens for `FILESTART`, creates output files inside `downloads/`, decodes incoming Base64 chunks to binary, and notifies the UI when the file is saved.                                    |
| 9   | `audioRecord.py`    | Client Side              | Procedural voice message recorder. Continuously pulls microphone audio frames using PyAudio in a background thread, compiles frames into a 44.1 kHz WAV file in `recordings/`, and plays WAV files asynchronously.   |
| 10  | `videoRecord.py`    | Client Side              | Procedural webcam video recorder. Captures hardware camera frames at ~20 FPS using OpenCV, encodes them into `recordings/output_video.avi` (XVID), and provides non-blocking playback in an OpenCV window.           |
| 11  | `audioCall.py`      | Client Side              | Real-time peer-to-peer audio calling. Dynamically allocates an ephemeral UDP socket, opens 16 kHz PyAudio input/output streams, and runs dual background loops to send and receive UDP audio directly between peers. |
| 12  | `videoCall.py`      | Client Side              | Real-time peer-to-peer video calling. Dynamically allocates an ephemeral UDP socket, captures camera frames, downscales to 320x240, compresses as JPEG (quality 40), and streams UDP payloads directly to the peer.  |
| 13  | `callManager.py`    | Client Side              | Signaling state machine for calls. Sends `CALL`, receives `INCOMING`, sends `ACCEPT`/`REJECT`, and orchestrates the automatic startup and teardown of media threads in `audioCall` and `videoCall`.                  |
| 14  | `gui.py`            | Client Side              | Monolithic desktop interface. Houses the dark-mode Tkinter GUI, `ChatClient` network reader, the 100 ms polling queue bridge (`_poll`), 3-column layout, and dialog modals.                                          |

---

### 2.2 Libraries Used & Their Exact Purpose

| Library / Module        | Source                                    | Purpose & Usage in Project                                                                                                                                                              |
| ----------------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `socket`                | Python Standard Library                   | Low-level networking. Creates TCP streaming sockets (`SOCK_STREAM`) for reliable text/files/signaling, and UDP datagram sockets (`SOCK_DGRAM`) for live low-latency calling.            |
| `threading`             | Python Standard Library                   | Concurrency management. Spawns non-blocking daemon worker threads for server clients, file reading, audio/video recording, UDP streaming, and uses `Lock` for mutex protection.         |
| `queue`                 | Python Standard Library                   | Thread-safe FIFO communication. Acts as the queue bridge transferring incoming network lines from background reader threads to the foreground Tkinter UI thread safely.                 |
| `tkinter`               | Python Standard Library                   | Graphical User Interface. Provides window containers, frames, buttons, scrollable text areas, entries, listboxes, dialogs, and the event-driven `root.mainloop()`.                      |
| `base64`                | Python Standard Library                   | Data encoding. Converts binary file chunks into ASCII-safe Base64 strings so they can be framed safely within standard newline-delimited TCP text streams.                              |
| `os`                    | Python Standard Library                   | Operating system interaction. Checks file existence, calculates file sizes (`os.path.getsize`), extracts base filenames, and creates `downloads/` and `recordings/` directories.        |
| `wave`                  | Python Standard Library                   | Audio file formatting. Reads and writes standard RIFF WAV headers, sample rates (44100 Hz), channels (stereo), and raw PCM audio frames.                                                |
| `time`                  | Python Standard Library                   | Timing and pacing. Regulates frame rates in video recording (~20 FPS via `time.sleep`) and timestamps events.                                                                           |
| `pyaudio`               | Third-Party (`pip install pyaudio`)       | PortAudio wrapper. Interfaces directly with hardware audio sound cards for microphone capture (`input=True`) and speaker playback (`output=True`) in both recording and live UDP calls. |
| `opencv-python` (`cv2`) | Third-Party (`pip install opencv-python`) | Computer vision. Captures live video from webcams (`VideoCapture`), writes video clips (`VideoWriter`), downscales images, encodes/decodes JPEG buffers, and renders playback windows.  |
| `numpy`                 | Third-Party (`opencv` dependency)         | Numerical arrays. Converts incoming raw UDP byte buffers into memory-contiguous image arrays (`np.frombuffer`) for real-time OpenCV decoding.                                           |

---

### 2.3 Core Functions: Signatures, Parameters & Types

#### 1. Transport & Connection (`protocol.py`)

- `Connection.__init__(self, sock: socket.socket, addr: tuple)`: Wraps raw client socket with reader file and mutex lock.
- `Connection.send(self, line: str) -> None`: Thread-safe line transmission. Appends `\n`, encodes UTF-8, and writes with `sock.sendall()`.
- `Connection.readline(self) -> str`: Reads one `\n`-terminated UTF-8 line. Returns empty string on disconnect.
- `Connection.close(self) -> None`: Performs socket `shutdown(SHUT_RDWR)` followed by `close()`.

#### 2. User & Room Directories (`clientRegistry.py`, `roomManager.py`)

- `clientRegistry.add_client(username: str, conn: Connection) -> bool`: Inserts user under lock. Returns `False` if name taken.
- `clientRegistry.remove_client(username: str) -> None`: Deletes user under lock.
- `clientRegistry.broadcast(line: str, sender: str = None) -> None`: Takes snapshot copy of clients under lock, then transmits `line` to all non-sender clients.
- `roomManager.join_room(room: str, username: str) -> None`: Adds user to room set under lock.
- `roomManager.leave_room(room: str, username: str) -> None`: Removes user from room set; purges room if empty.
- `roomManager.remove_user_from_all(username: str) -> None`: Purges a user from all rooms simultaneously when disconnecting.

#### 3. Server Handlers (`serverHandlers.py`)

- `handle_login(conn: Connection, parts: list[str]) -> str | None`: Validates username, checks duplicates, registers user, and triggers `USERS` broadcast.
- `handle_msg(conn: Connection, parts: list[str]) -> None`: Routes room message to all members in that room.
- `handle_pm(conn: Connection, parts: list[str]) -> None`: Routes 1-to-1 private message directly to recipient or returns offline error.
- `handle_file(conn: Connection, cmd: str, parts: list[str]) -> None`: Replaces target with sender identity and forwards file chunk line to destination user or room.
- `handle_call(conn: Connection, parts: list[str]) -> None`: Extracts caller IP (`conn.addr[0]`), appends to parameters, and routes `INCOMING` to callee.

#### 4. File Transfers (`fileTransfer.py`, `fileReceive.py`)

- `fileTransfer.send_file(client: ChatClient, target: str, filepath: str) -> None`: Spawns daemon thread to stream file.
- `fileTransfer.send_file_thread(client: ChatClient, target: str, filepath: str) -> None`: Reads 32 KB binary chunks, Base64 encodes, sends `FILECHUNK` lines, sends `FILEEND`, and updates `client.q`.
- `fileReceive.handle_file_start(sender: str, tid: str, filename: str, size: str, client: ChatClient) -> None`: Opens output stream in `downloads/`.
- `fileReceive.handle_file_chunk(sender: str, tid: str, b64_data: str, client: ChatClient) -> None`: Decodes Base64 chunk and writes binary bytes to disk.
- `fileReceive.handle_file_end(sender: str, tid: str, client: ChatClient) -> None`: Closes file stream and notifies UI chat of success.

#### 5. Audio & Video Recording (`audioRecord.py`, `videoRecord.py`)

- `audioRecord.start() -> None`: Initializes PyAudio stream (44.1 kHz, stereo) and starts background recording thread.
- `audioRecord.stop() -> str`: Halts recording, compiles raw PCM frames into `recordings/voice.wav`, and returns file path.
- `audioRecord.play_wav(filepath: str) -> None`: Spawns daemon thread to read and push WAV frames to speakers.
- `videoRecord.start() -> None`: Opens webcam (ID `0`), initializes OpenCV `VideoWriter` (XVID, 20 FPS), and starts frame capture loop.
- `videoRecord.stop() -> str`: Halts capture loop, releases camera and writer, and returns saved file path `recordings/output_video.avi`.
- `videoRecord.play_video(filepath: str) -> None`: Spawns daemon thread to render video frames in OpenCV window.

#### 6. Real-Time Calling (`audioCall.py`, `videoCall.py`, `callManager.py`)

- `audioCall.get_port() -> int`: Binds UDP socket to port `0` and returns the ephemeral port assigned by the OS.
- `audioCall.start(peer_ip: str, peer_port: int) -> None`: Opens mic/speaker PyAudio streams (16 kHz, mono) and starts UDP send/recv loops.
- `audioCall.stop() -> None`: Closes audio streams and UDP socket.
- `videoCall.get_port() -> int`: Binds UDP socket to port `0` and returns assigned ephemeral port.
- `videoCall.start(peer_ip: str, peer_port: int) -> None`: Opens webcam, launches downscaling/JPEG compression send loop, and launches UDP receive/display loop.
- `videoCall.stop() -> None`: Releases camera, closes UDP socket, and destroys OpenCV windows.
- `callManager.start_call(client: ChatClient, peer: str, mode: str) -> None`: Binds local UDP ports and sends `CALL|peer|mode|aport|vport` over TCP.
- `callManager.accept_call(client: ChatClient, caller: str, mode: str, caller_ip: str, caller_aport: str, caller_vport: str) -> None`: Sends `ACCEPT` and immediately launches local UDP media streams targeting caller IP and ports.
- `callManager.end_call(client: ChatClient) -> None`: Sends `ENDCALL` over TCP and halts local audio/video media threads.

#### 7. GUI Core & Polling (`gui.py`)

- `ChatClient.connect(self, host: str, port: int, timeout: float = 5.0) -> None`: Connects TCP socket, opens UTF-8 reader, and starts background thread.
- `ChatClient._reader(self) -> None`: Continuous loop reading lines and pushing them into `self.q`.
- `App._poll(self) -> None`: Scheduled every 100 ms via `root.after()`. Drains `client.q` and passes each line to `_dispatch(line)`.
- `App._dispatch(self, line: str) -> None`: Splits line by `|` and routes commands (`USERS`, `MSG`, `PM`, `FILE*`, `INCOMING`, etc.) to GUI callbacks.

---

## Part 3: Step-by-Step Project Report Structure

When assembling your report document (Word/PDF), format each chapter following the layout, detailed textual instructions, and GUI screenshot placeholders specified below.

---

### CHAPTER 1: Introduction & System Objectives

- **1.1 Background**: Problem statement of real-time communication across local area networks (LAN). Comparison of centralized client-server architectures versus peer-to-peer (P2P) topologies.
- **1.2 Core Objectives**:
  - Implement a scalable TCP server handling 3+ concurrent clients simultaneously without blocking.
  - Implement dynamic chat rooms (`#general`, custom rooms) and direct 1-to-1 Private Messages (`PM`).
  - Provide non-blocking base64 chunked file transfers (text, pictures, video).
  - Enable recording and playback of voice messages (`.wav`) and short video clips (`.avi`).
  - Provide low-latency live voice and video calling over direct UDP channels.
  - Maintain a responsive GUI that avoids blocking the Tkinter event loop.

---

### CHAPTER 2: System Architecture & Network Protocols

- **2.1 Architectural Overview**:

  > **[DIAGRAM PLACEHOLDER 1: High-Level System Architecture]**
  > _Insert a clear visual diagram illustrating:_
  >
  > 1. Client A and Client B connected to Central Server over TCP (port 5000).
  > 2. TCP carrying control traffic: Chat messages, Room commands, File chunks, and Call signaling.
  > 3. Direct Peer-to-Peer UDP media transmission between Client A and Client B for Audio & Video calls.

- **2.2 Protocol Framing & Specification**:
  _Textual Detail_: Explain why TCP is a byte stream without native message boundaries, and why newline-delimited framing (`\n`) with pipe separators (`|`) was chosen. Explain how `partition("|")` and fixed-split rules prevent user text from breaking commands.

  _Include Protocol Tables_:
  - **Client to Server**: `LOGIN|user`, `MSG|room|text`, `PM|user|text`, `JOIN|room`, `LEAVE|room`, `FILESTART`, `FILECHUNK`, `FILEEND`, `CALL|user|mode|aport|vport`, `ACCEPT|caller|aport|vport`, `REJECT|caller|reason`, `ENDCALL|other`.
  - **Server to Client**: `USERS|list`, `MSG|room|sender|text`, `PM|sender|text`, `INFO|msg`, `ERROR|msg`, `FILESTART|sender|...`, `INCOMING|caller|mode|ip|aport|vport`, `ACCEPTED|callee|ip|aport|vport`, `REJECT|callee|reason`, `ENDCALL|other`.

---

### CHAPTER 3: Server Design & Concurrency

- **3.1 Accept Loop & Lifecycle Management**:
  _Textual Detail_: Explain how `server.py` binds to `0.0.0.0:5000` with `SO_REUSEADDR`, listens for connections, and immediately starts a daemon thread `handle_client(sock, addr)` for each client.
  _Textual Detail_: Emphasize the `try/finally` block ensuring users are automatically purged from `clientRegistry` and `roomManager` on disconnect or sudden network drops.

- **3.2 Concurrency & Race Condition Prevention**:
  _Textual Detail_: Explain how shared state is protected:
  - `clients = {}` in `clientRegistry.py` protected by `threading.Lock()`.
  - `rooms = {}` in `roomManager.py` protected by `threading.Lock()`.
  - Snapshot broadcasting to eliminate deadlocks during network I/O.
  - Per-connection send lock in `protocol.py` ensuring multi-threaded writes do not interleave bytes.

- **3.3 Working Screenshot**:
  > **[GUI / TERMINAL SCREENSHOT 1: Active Server Daemon Console]**
  > _Capture the running `server.py` console window showing:_
  >
  > - `Chat Server running on 0.0.0.0:5000`
  > - Multiple clients connecting (`[Connected] ('192.168.1.X', ...)`).
  > - Authenticated logins and clean disconnect logs.

---

### CHAPTER 4: Client Architecture & GUI Layout

- **4.1 Decoupled Modular Architecture**:
  _Textual Detail_: Explain why UI widgets and network/media logic are strictly separated. The GUI only handles rendering and event capture; backend modules handle networking procedurally.

- **4.2 Tkinter Thread-Safety via Event Queue**:
  _Textual Detail_: Detail how background reader threads deposit network events into `queue.Queue()`, and `App._poll()` drains them via `root.after(100, self._poll)`.

- **4.3 Working Screenshots**:

  > **[GUI SCREENSHOT 2: Client Login Window]**
  > _Show the login interface displaying Server Host, Port, Username entry field, and the "Connect" button._

  > **[GUI SCREENSHOT 3: Main Dashboard Overview]**
  > _Show the full main page after successful login featuring:_
  >
  > - Left Panel: Rooms list (`#general`), Join/Leave inputs, logged-in status.
  > - Center Panel: Header title, media toolbar buttons (`File`, `Voice Rec`, `Video Rec`, `Call Audio`, `Call Video`, `End Call`, `Settings`), chat history display, emoji picker button, and message input bar.
  > - Right Panel: Active `ONLINE` users list showing all connected clients.

---

### CHAPTER 5: Messaging & Room Management

- **5.1 Public Room Messaging & Isolation**:
  _Textual Detail_: Walk through the life cycle of a message in `#general`. Explain how `roomManager.py` isolates messages so that users in `#study` never receive messages from other rooms.

- **5.2 Private 1-to-1 Messaging (PM)**:
  _Textual Detail_: Explain double-clicking an online user in the right list, switching the context to `@username`, and the server routing the `PM` exclusively to the intended recipient.

- **5.3 Working Screenshots**:

  > **[GUI SCREENSHOT 4: Multi-Client Group Chat Session]**
  > _Capture two client windows side-by-side chatting concurrently in `#general`._

  > **[GUI SCREENSHOT 5: Custom Room Creation & Join]**
  > _Show a user entering a new room name (e.g. `study`), clicking "Join", and chatting with room isolation._

  > **[GUI SCREENSHOT 6: 1-to-1 Private Chat Mode]**
  > _Show a private chat session between two users with distinctive private message styling (`pm_bg` tint)._

  > **[GUI SCREENSHOT 7: Interactive Emoji Picker Popup]**
  > _Show the emoji palette open above the composition bar, with emojis inserted into the message._

---

### CHAPTER 6: File & Media Sharing

- **6.1 Base64 Chunked File Streaming**:
  _Textual Detail_: Explain why large files are split into 32 KB chunks and Base64-encoded to guarantee constant memory usage and smooth streaming through the socket pipeline.

- **6.2 Audio & Video Recording Pipelines**:
  _Textual Detail_: Explain procedural microphone capture to `recordings/voice.wav` via PyAudio, and webcam capture to `recordings/output_video.avi` via OpenCV.

- **6.3 Working Screenshots**:

  > **[GUI SCREENSHOT 8: File Selection & Upload Progress]**
  > _Show the system file chooser modal and the chat window displaying `Uploading file [filename] to [target]...`._

  > **[GUI SCREENSHOT 9: File Download Confirmation & Storage]**
  > _Show the receiving client's chat showing `File [filename] saved to downloads/`, along with the Windows Explorer window displaying the file inside `downloads/`._

  > **[GUI SCREENSHOT 10: Voice Recording Dialog in Action]**
  > _Show the `Voice Recorder` popup window with `Recording...` status, and the `Saved!` / `Playing...` state with Start, Stop, and Play buttons._

  > **[GUI SCREENSHOT 11: Video Clip Recording Dialog & Playback]**
  > _Show the `Video Recorder` modal along with the OpenCV camera playback window (`Playback (Press q to close)`)._

---

### CHAPTER 7: Real-Time Audio & Video Calling

- **7.1 Signaling vs. Direct Media Path**:
  _Textual Detail_: Explain the distinction between signaling over TCP (via the server) and high-speed streaming over direct peer-to-peer UDP sockets.

- **7.2 Direct Peer-to-Peer UDP Pipeline**:
  _Textual Detail_: Explain dynamic port allocation (`sock.bind(("", 0))`), frame compression (320x240, JPEG quality 40), and continuous UDP streaming between clients.

- **7.3 Working Screenshots**:

  > **[GUI SCREENSHOT 12: Outgoing Call Initiation]**
  > _Show Client A clicking "Call Video" or "Call Audio", with the chat header indicating `Calling [user] (Video)...`._

  > **[GUI SCREENSHOT 13: Incoming Call Accept/Reject Dialog]**
  > _Show Client B displaying the modal dialog: `Incoming VIDEO call from [caller]. Accept?` with Yes / No options._

  > **[GUI SCREENSHOT 14: Active 2-Way Live Video Call Window]**
  > _Show the active OpenCV live video window rendering the real-time webcam stream over UDP._

  > **[GUI SCREENSHOT 15: Clean Call Termination]**
  > _Show the user clicking "End Call", the video window closing, and the chat status displaying `Call ended`._

---

### CHAPTER 8: Testing, Verification & Results

- **8.1 Verification Matrix**:
  _Include the verified test table:_
  | Test ID | Test Scenario | Expected Outcome | Result |
  |---|---|---|---|
  | T1 | Concurrent Server Logins | 3+ users online, lists synced | PASS |
  | T2 | Room Isolation | Messages in `#study` invisible to `#general` | PASS |
  | T3 | Private Messaging | Only intended recipient receives PM | PASS |
  | T4 | 50 MB File Transfer | File intact, MD5/SHA256 matches | PASS |
  | T5 | Voice Recording & Playback | `.wav` recorded and playable | PASS |
  | T6 | Real-Time Audio Call | 2-way microphone/speaker UDP transmission | PASS |
  | T7 | Real-Time Video Call | 2-way webcam UDP transmission | PASS |
  | T8 | Unexpected Client Disconnect | Clean removal from registry and rooms | PASS |

- **8.2 Network Evidence**:
  > **[GUI / NETWORK SCREENSHOT 16: Wireshark Packet Trace]**
  > _Capture a Wireshark session displaying:_
  >
  > - Formatted TCP lines (`MSG|...`, `FILECHUNK|...`).
  > - Continuous high-throughput UDP packet flow between the two client IP addresses during an active call.

---

### CHAPTER 9: Settings, Graceful Exit & Limitations

- **9.1 Settings & Network Diagnostics**:
  _Textual Detail_: Explain the Settings modal displaying local username, remote server socket address, and network diagnostics.

- **9.2 Graceful Teardown**:
  _Textual Detail_: Explain window close event interception, closing background threads, terminating media streams, and disconnecting cleanly from the server.

- **9.3 Working Screenshots**:
  > **[GUI SCREENSHOT 17: Settings Modal Dialog]**
  > _Show the Settings dialog displaying the current Username and Server IP:Port connection details._

---

## Part 4: Presentation & Demo Guide

### 4.1 Slide Deck Structure (10-12 Slides)

1. **Title Slide**: Project Name, Course Title, Student Names, Registration IDs.
2. **Problem Statement & Objectives**: Why build custom sockets instead of relying on third-party frameworks.
3. **High-Level Architecture**: Client-Server TCP Control vs. Peer-to-Peer UDP Media (Insert Architecture Diagram).
4. **File Structure & Library Breakdown**: Summary tables from Part 2 detailing modular layout.
5. **Protocol Design & Framing**: Newline framing, command syntax, and error handling.
6. **Multi-threading Model**: Breakdown of worker threads, mutex locks, and the Tkinter queue bridge.
7. **Group & Private Chatting**: GUI screenshots showing room segregation and private messaging.
8. **File & Media Streaming**: GUI screenshots of file transfers, voice recorder, and video clip recorder.
9. **Real-Time Calling**: GUI screenshots of call signaling, incoming call modal, and active video streaming.
10. **Test Verification & Wireshark Capture**: Packet trace proving TCP control and direct UDP media.
11. **Conclusion & Future Enhancements**: TLS encryption, database persistence, and STUN/TURN integration.

---

### 4.2 Live Demo Step-by-Step Script

Follow this script during the viva examination:

1. **Step 1: Launch the Server**
   - Run `python server.py`.
   - Point out: _“The server binds to port 5000 and is now listening for incoming TCP client connections.”_

2. **Step 2: Connect Multiple Clients**
   - Open Client 1 (`Alice`) and Client 2 (`Bob`).
   - Point out: _“Notice how both windows instantly reflect each other in the Online Users list upon login.”_

3. **Step 3: Group Chat & Room Creation**
   - Send messages in `#general`.
   - Create and join room `#study`. Send a message and show that only members in `#study` can read it.

4. **Step 4: Private Messaging (PM)**
   - Double-click `Bob` on Alice's client.
   - Send private messages and demonstrate the private chat visual tint.

5. **Step 5: File Transfer**
   - Click **File**, select a file, and send it.
   - Show the file appearing inside the `downloads/` directory of the recipient.

6. **Step 6: Voice & Video Recording**
   - Open **Voice Rec**, record a message, and play it.
   - Open **Video Rec**, record a short webcam video clip, and play it back.

7. **Step 7: Audio & Video Call Demonstration**
   - In private chat with Bob, click **Call Video**.
   - Show the incoming call dialog on Bob's screen. Click **Yes**.
   - Show the live UDP video window streaming between both laptops.
   - Click **End Call** to verify immediate, clean termination of the UDP stream.

8. **Step 8: Graceful Disconnect**
   - Close Alice's window.
   - Point out Bob's client automatically removing Alice from the user list with zero server errors.

---

### 4.3 Viva Defense Quick-Reference Cheat Sheet

| Question                                                              | Winning Technical Answer                                                                                                                                                                                                                    |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| _Why use TCP for chat/files but UDP for calls?_                       | TCP guarantees ordering and packet delivery via acknowledgments and retransmissions, which text and files need. Audio/video calls require real-time playback where a dropped packet is preferable to blocking delays.                       |
| _How do you prevent message corruption in TCP streams?_               | Sockets transmit raw bytes, not discrete messages. We delimit messages using `\n` and protect all `sock.sendall()` calls with a per-connection `threading.Lock`.                                                                            |
| _How is the GUI kept responsive during file transfers?_               | File I/O and transmission run on a dedicated worker thread. The thread deposits status updates into a `queue.Queue`, which Tkinter safely reads via `root.after()`.                                                                         |
| _How do clients connect for calls if the server doesn't relay media?_ | The server acts purely as a signaling broker. The clients allocate local UDP ports, exchange their IP and port numbers over the existing TCP connection, and then stream UDP directly peer-to-peer.                                         |
| _What happens if a user crashes or closes unexpectedly?_              | The server's `readline()` call returns an empty string `""`, triggering the `finally` block in `handle_client`. The user is cleanly purged from `clientRegistry` and all rooms, and a fresh `USERS` list is broadcast to remaining clients. |
