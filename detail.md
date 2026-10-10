# Real-Time Multi-User Chat Application: Complete Project Detail

Python socket programming, multithreading, Tkinter GUI. This document explains the whole system, every file you need, how each file works internally, and how the Tkinter GUI links everything together.

## 0. Strict Constraints for Code Editors & AI Assistants

> **CRITICAL RULE:** Before making *any* changes to this project, you (the code editor or AI assistant) **MUST** read this detail.md file in its entirety to understand the established architecture and rules.

When modifying or extending this codebase, you must adhere strictly to the following constraints:

1. **Maintain Extreme Simplicity:** Always use the absolute simplest and easiest syntax and logic possible. Avoid overly clever, highly abstracted, or complex Python features if a basic approach works perfectly well.
2. **Respect the Existing Approach:** If a user adds a new file or feature that utilizes the current architecture/logic and it is not 100% working, **DO NOT** rewrite the file or change the core approach. Your job is only to debug and fix the specific issues to make it correct and working within the bounds of the existing logic.
3. **Simple Additions Only:** When the user asks you to add a new feature, always choose the most straightforward, easiest-to-understand approach and logic. Do not over-engineer or introduce unnecessary external libraries.

---

## 1. What the project must do (from the brief)

| # | Requirement | Where it is built |
|---|---|---|
| 1 | 3+ clients on the same LAN/Wi-Fi | `server.py`, `networkClient.py` |
| 2 | Real-time message transmission | `messageTransfer.py`, `serverHandlers.py` |
| 3 | Display of active clients | `USERS` broadcast, `clientRegistry.py`, `gui.py` |
| 4 | Message, voice message, file, image, video sharing | `messageTransfer.py`, `filesTransfer.py`, `audioRecord.py`, `videoRecord.py` |
| 3 | Group chat with rooms (create, join, leave) | `roomManager.py`, `messageTransfer.py` |
| 4 | Private one-to-one chat | `serverHandlers.py`, `messageTransfer.py` |
| 5 | Voice and video calling | `callManager.py`, `audioCall.py`, `videoCall.py` |
| 6 | Python sockets + efficient threads | whole project, see section 10 |
| 6 | Modular and scalable | one file per feature, one protocol, one dispatcher |
| Optional | GUI (1 mark) | `gui.py` |

**Rubric mapping**

| Rubric criterion | Marks | Files that earn it |
|---|---|---|
| Functionality | 4 | all features working together |
| Group and private chat | 3 | `roomManager.py`, `messageTransfer.py`, `serverHandlers.py` |
| File and media sharing | 2 | `filesTransfer.py`, `audioRecord.py`, `videoRecord.py` |
| Thread management and network efficiency | 3 | `server.py`, `networkClient.py`, call modules, locks |
| Code structure and documentation | 2 | modular layout, comments, this document, the report |
| Optional feature | 1 | `gui.py` |

---

## 2. The big picture

```
 +--------------------------- CLIENT (each laptop) ---------------------------+
 |                                                                            |
 |  gui.py  (Tkinter: login page, main page, call window)                     |
 |    |  button clicks                          ^  screen updates             |
 |    v                                         |                             |
 |  messageTransfer.py   filesTransfer.py   callManager.py                    |
 |       |                    |   ^              |   \                        |
 |       |             audioRecord.py            |    audioCall.py (UDP)      |
 |       |             videoRecord.py            |    videoCall.py (UDP)      |
 |       v                    v                  v                            |
 |  networkClient.py (socket, receive thread,  |
 |                                  queue, dispatcher)                        |
 +----------------------------------|-----------------------------------------+
                                    |  TCP (chat, files, call signaling)
                                    v
 +--------------------------- SERVER (one laptop) ----------------------------+
 |  server.py  (accept loop, one thread per client, dispatch table)           |
 |     -> serverHandlers.py  (what to do for each message type)               |
 |     -> clientRegistry.py  (who is online)                                  |
 |     -> roomManager.py     (who is in which room)                           |
 +----------------------------------------------------------------------------+

 Voice/video media does NOT go through the server:
   client A  <==== UDP (audio port, video port) ====>  client B
```

Three rules hold the design together:

1. **TCP for everything reliable** (chat, files, call set-up). **UDP only for live audio and video.**
2. **The server only routes.** It never reads, stores or processes media. 
3. **One protocol, one dispatcher.** Every feature module registers handlers for its own message types. Adding a feature never changes existing modules.

---

## 3. Every file you need

### 3.1 Folder layout (flat, on purpose)

```
chatproject/
├── config.py
├── protocol.py
├── requirements.txt
│
├── server.py                 <- run on the server laptop
├── clientRegistry.py
├── roomManager.py
├── serverHandlers.py
│
├── networkClient.py
├── messageTransfer.py
├── filesTransfer.py
├── audioRecord.py
├── videoRecord.py
├── audioCall.py
├── videoCall.py
├── callManager.py
├── gui.py                    <- run on every laptop
│
├── downloads/                (created automatically)
├── recordings/               (created automatically)
└── tests/                    (optional)
```

**Why flat:** Python finds `import protocol` only if `protocol.py` is in the same folder as the script you run (or on the path). Subfolders add import problems that waste time and teach nothing about networking. The file names already group the code.

### 3.2 Required files (16)

| # | File | Side | Purpose in one line |
|---|---|---|---|
| 1 | `config.py` | both | Every constant (port, sizes, timeouts, switches) in one place |
| 2 | `protocol.py` | both | `Connection` class: line framing, thread-safe send, safe close |
| 3 | `requirements.txt` | tool | `pyaudio`, `opencv-python`, `` |
| 4 | `server.py` | server | Accept loop, thread per client, dispatch table, cleanup |
| 5 | `clientRegistry.py` | server | Thread-safe `username -> Connection` and broadcast |
| 6 | `roomManager.py` | server | Thread-safe `room -> set of users` |
| 6 | `serverHandlers.py` | server | One function per message type (login, msg, pm, file relay, call signaling) |
| 7 | `networkClient.py` | client | `ChatClient` (socket, receive thread, queue) and `Dispatcher` |
| 8 | `messageTransfer.py` | client | Send and receive chat, rooms, user list, info and errors |
| 10 | `filesTransfer.py` | client | Chunked file sending and receiving with progress |
| 11 | `audioRecord.py` | client | Record voice message to WAV, play WAV |
| 12 | `videoRecord.py` | client | Camera access and short video clip recording |
| 13 | `audioCall.py` | client | Live audio over UDP |
| 14 | `videoCall.py` | client | Live video over UDP |
| 15 | `callManager.py` | client | Call signaling state machine, starts and stops the media modules |
| 16 | `gui.py` | client | Tkinter login page, main page, call window, and all the wiring |

### 3.3 Optional files

| File | Why |
|---|---|
| `loginPage.py`, `mainPage.py`, `callWindow.py` | Split `gui.py` when it grows past about 500 lines |
| `tests/testProtocol.py`, `testRooms.py`, `testFileChunks.py` | Evidence for the testing chapter |
| `README.md` | How to install and run (the evaluator reads this first) |
| `docs/` | Report, diagrams, screenshots, bug log |

### 3.4 If time runs short

Without voice messages, video recording and calls you can drop `audioRecord.py`, `videoRecord.py`, `audioCall.py`, `videoCall.py` and `callManager.py`. That leaves 11 files and still covers chat, rooms, private chat, active users, file and image sharing, and threads. Cut calls last-but-one and video first.

---

## 4. Libraries

| Library | Install | Used by |
|---|---|---|
| `socket`, `threading`, `queue`, `struct`, `time`, `os`, `uuid`, `base64`, `wave` | built in | most files |
| `tkinter` | built in | `gui.py` |
| `pyaudio` | `pip install pyaudio` | `audioRecord.py`, `audioCall.py` |
| `opencv-python` (installs `numpy`) | `pip install opencv-python` | `videoRecord.py`, `videoCall.py` |

`requirements.txt`:

```
pyaudio
opencv-python

```

Windows: if `pyaudio` fails, use `pip install pipwin` then `pipwin install pyaudio`. Use Python 3.10 or newer.

---

## 5. Concepts you must understand before coding

| Concept | Why it matters here |
|---|---|
| **TCP is a byte stream** | No message boundaries. We end every message with `\n` and read with `readline()`. |
| **Blocking calls** | `accept()`, `readline()`, `input()` pause the thread. Each waiting job needs its own thread. |
| **Thread per client** | The server never gets stuck on one user. |
| **Race condition and lock** | `clients` and `rooms` are shared by all threads, so they are protected. |
| **Concurrent sends need a lock too** | Two threads calling `sendall` on the same socket can interleave their bytes and corrupt lines. `Connection.send` locks. |
| **UDP** | No connection, no ordering, no retransmission. Perfect for live media, wrong for files. |
| **Signaling vs media** | Set up the call over TCP (who, which ports), stream over UDP. |
| **Tkinter is not thread-safe** | Only the main thread touches widgets. Other threads post to a queue. |

---

## 6. The protocol (version 2)

### 6.1 Framing and parsing rules

- One message = one line of UTF-8 text ending in `\n`.
- Format: `TYPE|field|field|...|lastField`.
- **Free text is always the last field**, so it may contain `|` safely.
- Parse with `kind, _, rest = line.partition("|")`, then each handler does `rest.split("|", n)` with the right `n`. Never use a plain `split("|")` on a line containing user text.
- Remove newlines from user text before sending (`text.replace("\n", " ")`). The Tkinter `Entry` cannot contain newlines anyway.
- Usernames and room names must not contain `|`, spaces at the ends, or start with `#`. Max 20 characters.
- A target starting with `#` means a room (`#study`). Otherwise it is a username.

### 6.2 Client to server

| Line | Meaning |
|---|---|
| `LOGIN\|name` | Log in with a username |
| `MSG\|room\|text` | Message to a room you have joined |
| `PM\|user\|text` | Private message |
| `JOIN\|room` | Join (and create if new) |
| `LEAVE\|room` | Leave a room |
| `ROOMS\|` | Ask for the room list |
| `FILESTART\|target\|tid\|filename\|size` | Begin a file transfer. `tid` is a short random id. |
| `FILECHUNK\|target\|tid\|data` | One chunk (base64) |
| `FILEEND\|target\|tid` | File finished |
| `FILEABORT\|target\|tid` | Sender cancelled or failed |
| `CALL\|target\|mode\|audioPort\|videoPort` | Start a call. `mode` is `audio` or `video`. `videoPort` is `0` for audio calls. |
| `ACCEPT\|caller\|audioPort\|videoPort` | Accept an incoming call |
| `REJECT\|caller\|reason` | Reject (`declined`, `busy`) |
| `ENDCALL\|other` | Hang up |

### 6.3 Server to client

| Line | Meaning |
|---|---|
| `USERS\|ali,sara,bob` | Current online users, sent to everyone on every login and logout |
| `ROOMLIST\|general:3,study:1` | Rooms with member counts |
| `MSG\|room\|sender\|text` | Room message |
| `PM\|sender\|text` | Private message |
| `INFO\|text` | Informational (joined, left) |
| `ERROR\|text` | Something failed (offline user, not in room, bad username) |
| `FILESTART\|sender\|tid\|filename\|size` | Incoming file |
| `FILECHUNK\|sender\|tid\|data` | Chunk |
| `FILEEND\|sender\|tid` | Done |
| `FILEABORT\|sender\|tid` | Sender cancelled |
| `INCOMING\|caller\|mode\|ip\|audioPort\|videoPort` | Someone is calling you. The server adds the caller's IP. |
| `ACCEPTED\|callee\|ip\|audioPort\|videoPort` | Your call was accepted. The server adds the callee's IP. |
| `REJECT\|callee\|reason` | Your call was rejected |
| `ENDCALL\|other` | The other side hung up |

The server always **replaces the target with the sender** when forwarding (`PM|sara|hi` from ali arrives at sara as `PM|ali|hi`), so a client can never fake who a message is from.

### 6.4 Local events (never sent over the network)

Worker threads cannot touch the GUI, so they put local events into the same queue, prefixed with `@`:

| Event | Posted by | Meaning |
|---|---|---|
| `@DISCONNECTED\|` | receive thread | The server connection closed |
| `@FILEPROGRESS\|tid\|percent` | file sender thread | Progress for the progress bar |
| `@FILESENT\|tid\|name` | file sender thread | Upload finished |
| `@FILEFAILED\|tid\|reason` | file sender thread | Upload failed |
| `@VOICEREADY\|path` | voice recorder thread | Recording finished |
| `@CALLTIMEOUT\|` | ring timer | Nobody answered in 30 seconds |
| `@PEERLOST\|` | call watchdog | No media packets for 5 seconds |

The dispatcher treats them exactly like server lines, so handling is uniform.

---

## 7. Fixes to the earlier starter code

If you already copied the first `protocol.py` and `server.py` I gave you, change these four things. They are real bugs that only show up in demos.

| Problem in the starter | Symptom | Fix (already included below) |
|---|---|---|
| `sock.makefile("r")` uses the system encoding, but `.encode()` uses UTF-8 | Non-English text or emoji turns into garbage on Windows | `makefile("r", encoding="utf-8")` |
| `sock.close()` while a `makefile` reader exists does not really close the socket | Closed client stays "online" (ghost user) | `shutdown(SHUT_RDWR)` before `close()` |
| `sendall` called from several threads on one socket | Two messages interleave into one broken line | Per-connection send lock |
| `split("\|", 2)` on every line | File and call messages with more fields break | `partition` plus per-handler `split` |

---

## 8. Shared files

### 8.1 `config.py`
**Logic and Working:**
This file acts as the central repository for all configuration constants, ensuring that no magic numbers are hardcoded throughout the project. It defines network settings (such as the server port and connection timeouts), data constraints (maximum username length and maximum file upload sizes), and feature toggles. By isolating these values, the application's behavior can be easily tuned during testing or deployment without modifying the core logic. 

### 8.2 `protocol.py`
**Logic and Working:**
This file manages reliable, thread-safe TCP communication by encapsulating the raw network socket into a `Connection` class. 
- **Framing Strategy:** It uses newline characters (`\n`) to delimit messages, treating the continuous TCP stream as a sequence of discrete textual lines. 
- **Thread Safety:** It employs a threading lock during the `send` operation. This ensures that if multiple threads attempt to send messages simultaneously (e.g., a file transfer thread and a chat thread), their bytes don't interleave and corrupt the protocol lines. 
- **Graceful Shutdown:** The termination logic specifically calls a socket shutdown before closing. This immediately interrupts any blocking read operations in background threads, ensuring a clean termination without leaving zombie threads waiting indefinitely.

---

## 9. Server files

### 9.1 `clientRegistry.py`
**Logic and Working:**
This module maintains the centralized state of all currently connected clients on the server.
- **State Tracking:** It uses a dictionary structure mapping authenticated usernames to their active `Connection` objects.
- **Concurrency Control:** It protects all state modifications (adding new users, removing disconnected users, and lookups) with a threading lock, as multiple client threads will be logging in and out concurrently.
- **Deadlock Avoidance:** The broadcast method employs a specific safety pattern: it takes a snapshot of the active connections, releases the lock, and *then* iterates over the snapshot to send data. This prevents a slow or broken client connection from freezing the entire server while holding the registry lock.

### 9.2 `roomManager.py`
**Logic and Working:**
Tracks which users are currently active in which chat rooms to facilitate group messaging.
- **State Tracking:** It maps room names to sets of usernames, automatically initializing a default "general" room. Sets are used to inherently prevent duplicate memberships.
- **Thread Safety:** Like the registry, all membership modifications are guarded by a lock to handle simultaneous join/leave requests from different threads.
- **Lifecycle Management:** It automatically deletes rooms when the last user leaves (except for the persistent "general" room) to prevent memory leaks. It also provides a robust cleanup method to completely purge a user from all rooms simultaneously when they disconnect unexpectedly.

### 9.3 `serverHandlers.py`
**Logic and Working:**
Acts as the routing and processing brain of the server. It maps inbound protocol commands (like `LOGIN`, `MSG`, `JOIN`) to specific handler functions.
- **Input Validation:** It sanitizes and validates inputs, ensuring usernames and room names meet formatting rules (no pipes, correct length) before accepting them.
- **Message Routing:** When a room message or private message is received, the handler validates the sender's membership, identifies the target recipients via the `ClientRegistry` and `RoomManager`, and forwards the message to the appropriate sockets.
- **Security Check:** The server systematically replaces the declared sender field in forwarded messages with the actual authenticated name tied to the socket connection. This completely prevents clients from spoofing their identities.
- **Stateless Relays:** For heavy operations like file transfers and call signaling, the server acts as a pure stateless relay. It simply forwards signaling data and binary chunks from the sender directly to the target without caching them in memory, keeping the server's footprint minimal.

### 9.4 `server.py`
**Logic and Working:**
The main entry point and daemon process for the chat server.
- **Socket Initialization:** It binds to `0.0.0.0` to accept connections from any network interface and configures the socket to reuse the address for quick development restarts.
- **Thread Spawning:** The main thread sits in an infinite loop listening for connections. For every new client, it spawns a dedicated daemon thread.
- **Client Lifecycle:** The client thread continuously reads lines from the TCP stream. It parses the command type, looks up the appropriate function in the `serverHandlers.py` dispatcher, and executes it.
- **Cleanup Guarantee:** It wraps the client loop in a strict `try/finally` block. This guarantees that whether a client disconnects cleanly, crashes, or suffers a network drop, they are safely removed from the registry and all rooms, and a global logout broadcast is sent to remaining users.

---

## 10. Client files

### 10.1 `networkClient.py`
**Logic and Working:**
Manages the client-side TCP connection and background message parsing.
- **Dispatcher Pattern:** It implements an event dispatcher mapping incoming message types to lists of callback functions. This decouples the network layer from the UI and feature modules, allowing them to subscribe to events dynamically.
- **Non-blocking Receiving:** The client opens the socket and immediately spawns a dedicated background thread whose sole job is to read lines from the socket.
- **Queueing Bridge:** The receive thread places incoming messages into a thread-safe queue. This strictly separates network I/O from UI updates, ensuring the graphical interface never hangs waiting for network packets.

### 10.2 `messageTransfer.py`
**Logic and Working:**
Handles the business logic for text-based chat operations.
- **Integration:** It registers listeners for chat-related events (`MSG`, `PM`, `USERS`, `INFO`, `ERROR`) with the central dispatcher.
- **Processing:** It formats outgoing text (stripping dangerous newlines) and processes the payload, and triggers the appropriate GUI callbacks provided during initialization.

### 10.3 `filesTransfer.py`
**Logic and Working:**
Manages the robust, non-blocking transfer of large files between clients.
- **Chunking Mechanism:** To prevent out-of-memory errors and server blocking, files are never loaded entirely into memory. Instead, they are read and sent in small chunks (e.g., 32 KB).
- **Background Uploading:** The upload process runs in an isolated background thread. It reads the file, encodes chunks (using Base64), transmits them, and periodically posts progress updates back to the GUI queue to drive a progress bar.
- **Receiving & Integrity:** The receiving logic listens for a file start header, opens a local file stream, and appends incoming chunks. Upon receiving the end signal, it verifies that the total bytes received perfectly match the size declared at the start. If they don't, the corrupted file is automatically deleted.

### 10.4 `audioRecord.py`
**Logic and Working:**
Handles interaction with the system microphone for recording voice messages.
- **Recording Loop:** It uses a dedicated background thread to continuously read audio frames from the hardware microphone into a growing memory buffer.
- **File Generation:** When the user stops the recording, the thread compiles the collected frames and uses the standard `wave` library to write them directly to a `.wav` file on the disk, complete with the correct sample rate and channel headers.
- **Playback:** Playback is also handled in a background thread that reads the `.wav` file chunks and pushes them to the speaker stream, ensuring the GUI remains entirely responsive while audio plays.

### 10.5 `videoRecord.py`
**Logic and Working:**
Manages webcam access and video clip recording using OpenCV.
- **Camera Initialization:** It captures the hardware webcam, utilizing specific flags on Windows to bypass slow startup routines.
- **Recording Loop:** It runs a loop for a specified duration, capturing frames, resizing them to a standard resolution to ensure consistency, and passing them to a video writer object.
- **File Output:** The writer encodes the frames into an `.mp4` file. The frame rate is manually regulated by forcing the thread to sleep between captures to match the target FPS.

### 10.6 `audioCall.py`
**Logic and Working:**
Manages live, two-way real-time audio streaming over UDP.
- **Dynamic Port Allocation:** It binds a UDP socket to port `0`, allowing the OS to assign an available ephemeral port. This port is later communicated to the peer via the TCP signaling server.
- **Tri-Thread Architecture:** It relies on three synchronized threads:
  1. **Send Thread:** Reads continuously from the microphone and transmits packets directly to the peer's IP and UDP port.
  2. **Receive Thread:** Listens for incoming UDP packets, pushing them into a buffer queue. It includes a watchdog mechanism to detect dropped connections if packets stop arriving.
  3. **Play Thread:** Drains the buffer queue and pushes audio to the speakers.
- **Latency Control:** The receive thread prioritizes low latency over absolute reliability by intentionally dropping the oldest packets if the playback buffer grows too large.

### 10.7 `videoCall.py`
**Logic and Working:**
Manages live, two-way video streaming over UDP.
- **Packet Sequencing:** It prepends a sequential 4-byte header to every video frame packet. This enables the receiver to intelligently detect and discard out-of-order or delayed frames, ensuring the video only moves forward.
- **Dynamic Compression:** It reads camera frames and dynamically lowers the JPEG compression quality in a loop until the resulting payload stays safely underneath the maximum UDP packet size limit.
- **Asynchronous Rendering:** The receiver decodes incoming JPEG bytes back into an image array, converts it to a base64 PNG, and stores it in memory protected by a lock. The main GUI thread repeatedly polls this variable on a timer to render the live video seamlessly.

### 10.8 `callManager.py`
**Logic and Working:**
Acts as the signaling brain that coordinates call state transitions.
- **State Machine:** It maintains the strict state of the call (IDLE, CALLING, RINGING, ACTIVE) and enforces business rules, such as automatically responding with a 'busy' signal if a second call arrives while one is active.
- **Signaling Negotiation:** It orchestrates the TCP signaling phase, exchanging IP addresses and the dynamically allocated UDP ports between the caller and callee via the central server.
- **Media Orchestration:** Once a call is accepted, it passes the negotiated peer IP and ports to the audio and video modules and instructs them to commence streaming.
- **Centralized Teardown:** It centralizes all call termination logic (hangup, rejection, ring timeouts, peer loss) into a single cleanup routine that guarantees the media modules are stopped and the state safely returns to IDLE.

---

## 10. `gui.py`: where everything is linked

### 10.1 Architecture and Design Logic
**Logic and Working:**
The graphical interface is a monolithic, single-file application built entirely on Python's standard `tkinter` library, utilizing no external widget toolkits. It manages the application window, layout switching, user input, and the event loop.
- **Unified Controller:** An `App` class acts as the central controller. It instantiates the network client, the UI pages, and the polling mechanism that bridges background network threads with the foreground UI.
- **Page Stacking:** Instead of opening multiple windows, the UI stacks a Login Page and a Main Page into the same layout grid. It switches contexts simply by raising the relevant frame to the top of the stack, preserving the state of hidden components.
- **Centralized Styling:** All visual attributes (colors, fonts, padding) are pulled from centralized dictionaries and factory functions. This ensures absolute visual consistency across all buttons, entries, and chat tags without repeating configuration code.

### 10.2 Threading and The Polling Loop
**Logic and Working:**
Tkinter, like most GUI frameworks, strictly requires that all UI updates occur on the main execution thread. 
- **The Queue Bridge:** The application solves this by never allowing network threads to touch the UI. Instead, the background network reader places raw incoming messages into a thread-safe queue.
- **The Drain Loop:** The main UI thread runs a continuous polling loop (triggered via Tkinter's `after` method every 100 milliseconds). This loop drains the queue, parses the commands, and routes them to the appropriate UI update functions.
- **Event Throttling:** To prevent the UI from freezing during high-volume events (like receiving thousands of file chunks), the poll loop artificially caps the number of messages it processes per tick.

### 10.3 UI Components and Layout Logic
**Logic and Working:**
The main interface is split into a rigid three-column grid designed for spatial stability.
- **Left Panel (Navigation):** Houses the room list and controls for joining/leaving. Clicking a room updates the central chat context. It uses placeholder text logic in the entry field to guide user input without requiring separate labels.
- **Center Panel (Content):** Contains the primary chat text area, a toolbar for media features, and the message composition bar. The chat area is kept strictly read-only, temporarily unlocking only when the program needs to insert new incoming text. It uses dynamic text tags to color-code sender names, system alerts, and private messages.
- **Right Panel (Users):** Displays the active roster of connected clients. It binds double-click events to users, allowing instant switching to a private messaging context.
- **Local Echo:** Because the server acts purely as a router and does not echo messages back to the sender, the UI manually inserts the user's outbound messages into the local chat history to provide immediate visual feedback.

### 10.4 Feature Integration and Dialogs
**Logic and Working:**
The UI provides modular integration points for advanced features.
- **Emoji Picker:** A custom floating overlay (a borderless top-level window) that calculates its position relative to the composition bar. It intercepts focus events to auto-close when the user clicks away, and inserts selected emoji directly at the text cursor's current index.
- **Settings and Alerts:** Utilizes modal dialogs that lock interaction with the main window until dismissed, ensuring the user acknowledges connection errors, incoming calls, or configuration details. 
- **Graceful Exit:** Intercepts window close events to send a formal disconnect signal to the server, shut down the network client, and destroy the UI elements in the correct order, ensuring the user doesn't leave a ghost connection behind.



---

---

## 11. End-to-end walk-throughs

### Login
1. User types name and IP, clicks Connect.
2. `ChatClient.connect` opens TCP and sends `LOGIN|ali`; the receive thread starts.
3. The server's accept loop creates a thread for this connection. `on_login` validates, adds `ali` to the registry and to room `general`.
4. The server broadcasts `USERS|ali,sara` to everyone.
5. The GUI queue receives `USERS|...`, the login page sees it, and the main page appears with the list filled in.

### Room message
1. Ali types "hello" in `#general` and presses Enter.
2. `MessageService.send_room` sends `MSG|general|text`. The GUI also shows "hello" in Ali's own chat.
3. The server's thread for Ali checks membership and sends `MSG|general|ali|text` to every other member.
4. Each receiver's receive thread queues the line; the poll loop dispatches it; `_on_msg` decrypts; the GUI shows `ali: hello`.

### File transfer
1. Ali clicks File and picks `photo.jpg` (240 KB).
2. A worker thread sends `FILESTART|sara|a1b2c3d4|photo.jpg|245760`.
3. It reads 32 KB at a time, sends `FILECHUNK|sara|a1b2c3d4|<data>`, and posts progress events.
4. The server relays each line to Sara with Ali's name in place of "sara".
5. Sara's `FileService` writes each decoded chunk to `downloads/photo.jpg`.
6. `FILEEND` arrives; the byte count matches; the GUI shows "Received photo.jpg".

### Voice message
Click Record, speak, click Stop. `VoiceRecorder.stop()` returns a `.wav` path. It goes through the file pipeline above. Sara's GUI sees `.wav` and shows a Play button, which calls `play_wav`.

### Voice or video call
1. Ali clicks Video Call in his chat with Sara. `CallService` creates an `AudioCall` and a `VideoCall`; their sockets bind random UDP ports (say 50123 and 50124).
2. Ali sends `CALL|sara|video|50123|50124` over TCP.
3. The server adds Ali's IP and sends Sara `INCOMING|ali|video|192.168.43.10|50123|50124`.
4. Sara's GUI asks Accept or Reject. On Accept, her `CallService` binds her own UDP ports and sends `ACCEPT|ali|50456|50457`.
5. The server adds Sara's IP and sends Ali `ACCEPTED|sara|192.168.43.11|50456|50457`.
6. Both sides call `start(peer_ip, peer_port)`. Microphone and camera frames now travel **directly** between the laptops over UDP. The server is no longer involved.
7. Either user clicks End: `ENDCALL` goes through the server, both sides stop their threads and close their sockets.

---

## 12. Threads, locks and shared data

### 12.1 Thread inventory

| Where | Thread | Count | Blocks on |
|---|---|---|---|
| Server | Main (accept loop) | 1 | `accept()` |
| Server | `handle_client` | 1 per client | `readline()` |
| Client | GUI main thread | 1 | `mainloop()` |
| Client | Receive thread | 1 | `readline()` |
| Client | File sender | 1 per upload | disk read, `sendall` |
| Client | Voice or video recorder | 1 per recording | microphone or camera |
| Client | Audio call | 3 per call | mic, socket, speaker |
| Client | Video call | 2 per call | camera, socket |
| Client | Ring timer | 1 per outgoing call | timer |

Example: 4 clients on the server means 5 server threads. A client in a video call has about 8 threads.

### 12.2 Locks

| Shared data | Lock | Where |
|---|---|---|
| `clients` dict | `ClientRegistry._lock` | server |
| `rooms` dict | `RoomManager._lock` | server |
| One socket written by many threads | `Connection._send_lock` | server and client |
| Latest video frames | `VideoCall._lock` | client |

### 12.3 Deadlock and freeze avoidance

- Each lock is held only for a dictionary operation, never during network I/O.
- Registry and room locks are never held at the same time.
- `broadcast` copies the list, releases the lock, then sends.
- Only one lock per call path, so no lock-ordering problem.

### 12.4 Why threads and not multiprocessing or asyncio

The server is I/O-bound and its threads must share the registry and rooms. Threads share memory directly, so a lock is enough. Separate processes would each have their own copy of `clients`. The GIL does not matter because the threads spend their time waiting on the network. The brief explicitly asks for threads.

---

## 13. Error handling matrix

| Situation | What happens |
|---|---|
| Wrong server IP or server down | `connect` raises `OSError` after at most 5 s; login page shows the error |
| Duplicate username | Server sends `ERROR` and closes; login page shows it |
| Server crashes mid-chat | Receive thread gets `""`, posts `@DISCONNECTED`; GUI returns to login |
| Client closes or crashes | Server's `readline` returns `""`; `finally` removes the user and rebroadcasts `USERS` |
| PM to an offline user | `ERROR\|user offline` shown in red |
| Message to a room you left | `ERROR\|you are not in room x` |
| Malformed line | `ERROR\|bad message format`, connection stays open |
| File sender disconnects mid-upload | Receiver never gets `FILEEND`; partial file stays open until the sender's `USERS` entry disappears (optional cleanup) or until the app exits |
| Corrupted chunk or wrong key | `decode_bytes` raises, file is discarded and deleted |
| File larger than the limit | Refused before sending |
| Peer unreachable during a call | `PEERLOST` after 5 s, call ends cleanly |
| Camera busy or missing | `VideoCall` runs receive-only; recording shows an error |
| Microphone missing | `pyaudio` raises on `open`; show a message instead of crashing |
| Nobody answers a call | Ring timeout after 30 s |

---

## 15. Testing

### 15.1 Test each module alone first

| Module | Standalone test |
|---|---|
| `protocol.py` | Two scripts exchange 1,000 lines; count that none are lost or merged |
| `roomManager.py` | `print`-based test: join, leave twice, duplicate join, delete empty room |
| `filesTransfer.py` | Send a 50 MB file between two clients on one laptop; compare checksums (`certutil -hashfile` or `sha256sum`) |
| `audioRecord.py` | Record 3 s, play back |
| `videoRecord.py` | Show the camera, record 3 s, open the file |
| `audioCall.py` | Loopback to your own port with headphones |
| `videoCall.py` | Loopback with a video file instead of the camera if needed |

This is why one file per feature pays off: each piece can be proven before the GUI exists.

### 15.2 System test table (copy into the report)

| ID | Feature | Steps | Expected | Actual | Pass |
|---|---|---|---|---|---|
| T1 | Login | Start server, log in as ali | Main page, ali in users list | | |
| T2 | Duplicate username | Second client uses ali | Error shown, stays on login | | |
| T3 | Active users | 4 clients log in, one closes | Lists update on all screens | | |
| T4 | Room chat | ali sends in general | All other members receive, once | | |
| T5 | Room isolation | sara joins study; ali sends in study | Only study members receive | | |
| T6 | Private chat | sara PMs ali | Only ali receives | | |
| T7 | Offline PM | PM to a closed client | Red "user offline" | | |
| T8 | Text file | Send .txt | Same checksum | | |
| T9 | Image | Send .jpg | Opens correctly | | |
| T10 | Video | Send .mp4 | Plays correctly | | |
| T11 | Large file | Send 50 MB | Completes, progress bar moves, GUI stays responsive | | |
| T12 | Voice message | Record, send | Plays on receiver | | |
| T13 | Voice call | Call, accept, talk | Both hear each other | | |
| T14 | Video call | Call, accept | Both see each other | | |
| T15 | Reject and busy | Reject; call a user already in a call | Correct message | | |
| T16 | Hang up | End from either side | Both sides return to idle | | |
| T19 | Server killed | Close server window | Clients return to login | | |
| T20 | 4 devices | 4 clients chat at once | No crash, no lost messages | | |

### 15.3 Evidence to collect for the report

- Server terminal screenshots showing the `[LOGIN]`, `[PM]`, `[FILE]`, `[CALL]` lines
- Wireshark screenshot of readable text to show the protocol in action
- Screenshots of every feature on two different laptops
- A short screen recording of the full demo as a backup

---

## 16. Build order (do not skip ahead)

| Phase | Build | Done when |
|---|---|---|
| 1 | `config.py`, `protocol.py`, `server.py`, `clientRegistry.py`, `roomManager.py`, `serverHandlers.py` (login, msg, pm, join, leave only) | Three console test clients chat |
| 2 | `networkClient.py`, `messageTransfer.py` | A script logs in and chats through the services |
| 3 | `gui.py`: login page, main page, messaging | Two windows chat, users list updates |
| 4 | `filesTransfer.py` + server file relay + File button | Text, image, video arrive intact |
| 3 | `audioRecord.py` + Voice button | Voice message plays on another laptop |
| 5 | `audioCall.py`, `callManager.py`, call handlers on the server | Two laptops talk |
| 6 | `videoRecord.py`, `videoCall.py`, `CallWindow` | Two laptops see each other |
| 6 | Full test on 4 clients, bug fixes, `README.md`, report, backup video | All 20 tests pass |

Test on two real laptops at the end of phases 3, 4, 7 and 8, not only at the end.

---

## 17. Demo and LAN setup

1. Same Wi-Fi on both laptops. A phone hotspot is the safest choice because college Wi-Fi often has "client isolation".
2. Start the server on laptop A and find its IP with `ipconfig`.
3. **Connect every client with that LAN IP**, including the client on laptop A (see section 9.3 for why).
4. Allow Python through Windows Firewall on **private networks** on both laptops. Calls need UDP, not just TCP.
5. `ping` from B to A before anything else.
6. Copy the same `key.key` to both laptops.
6. Four clients with two laptops: two client windows per laptop. Say honestly that some clients are separate processes on the same machine; each has its own socket and threads, so the networking is genuine. Two clients on one laptop cannot both use the camera for video.
7. Put the server terminal next to the app window so the log lines show the sockets working.

---

## 18. Report outline (documentation)

1. Introduction and objectives
2. System architecture (the diagram in section 2)
3. Protocol specification (the tables in section 6)
4. Server design: accept loop, registry, rooms, handlers, locks
5. Client design: network layer, dispatcher, services, queue
6. Chat module: rooms and private chat, flowcharts
7. File and media sharing: chunking, integrity check, voice messages, recording
8. Voice and video calls: signaling, UDP media, packet layout, watchdog
10. GUI design: pages, thread-safety with queue and `after`
10. Thread management and network efficiency (section 13)
11. Testing and results (section 15)
12. Challenges, limitations, future work
13. Contribution table and screenshots

---

## 19. Viva questions with short answers

| Question | Answer |
|---|---|
| Why TCP for chat and UDP for calls? | TCP guarantees order and delivery, which text and files need. A call needs low delay, and a late packet is worse than a lost one. |
| How do you separate messages in a TCP stream? | Each message is one line ending in `\n`, read with `readline()`. |
| Why a thread per client? | `readline()` blocks. Without a thread per client one idle user would stop everyone else being served. |
| What is a race condition and where could yours occur? | Two threads changing shared data at once. It could happen on `clients` and `rooms`, so both are behind locks. |
| Why a lock on `send`? | Two threads writing to one socket can interleave bytes and corrupt a line. |
| Why do you copy the list before broadcasting? | So the lock is not held during network I/O, which could freeze every thread. |
| How is a file transferred? | A header with name and size, then 32 KB chunks, then an end message. The receiver compares bytes received with the declared size. |
| How do you know a file is complete? | `FILEEND` arrived and the byte count equals the announced size. |
| Why chunks? | Constant memory, a progress bar, and the server thread is never blocked by one huge message. |
| How does a call start? | Signaling over TCP exchanges IPs and UDP ports through the server. Then the clients stream directly to each other over UDP. |
| Why does the server not carry the media? | Less load, lower delay, and it scales better. |
| What if UDP packets are lost? | Audio has a short glitch. Video frames carry sequence numbers, so late ones are dropped. |
| Why is Tkinter updated through a queue? | Tkinter is not thread-safe, so only the main thread touches widgets. |
| Why not multiprocessing? | The work is I/O-bound and needs shared state. Threads share memory and a lock is enough. |
| How would it scale? | Replace the thread per client with a thread pool or `asyncio`, add TLS, add a database for offline messages. |

---

## 20. Limitations and future work

- Video clips have no audio
- No echo cancellation or jitter buffer beyond a small queue
- Messages to offline users are not stored
- Files are not resumable after a disconnect
- Only one-to-one calls (no group calls)
- No user accounts or passwords
- Future: TLS sockets, SQLite message history, group calls, `asyncio` server, a web or mobile front end

---

## 21. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Other laptop cannot connect | Firewall or Wi-Fi isolation | Allow Python on private networks; use a hotspot; test with `ping` |
| `address already in use` | Old server still running | Close it; `SO_REUSEADDR` handles quick restarts |
| Ghost user stays online | Socket closed without `shutdown` | Use `Connection.close()` |
| Garbled non-English text | Encoding mismatch | `encoding="utf-8"` in `makefile` |
| Call connects but no sound or video | UDP blocked, or server-laptop client used `127.0.0.1` | Allow UDP in the firewall; connect with the LAN IP |
| Call goes silent after the peer restarts | `ConnectionResetError` kills the receive thread | Keep the `except ConnectionResetError: continue` |
| Video label stays blank | `PhotoImage` garbage-collected | Store it on `self` |
| GUI freezes during a file send | Sending in a button handler, or unbounded poll loop | Use the worker thread; cap the poll loop |
| `pyaudio` will not install | Missing wheel | `pipwin install pyaudio` |
| Camera does not open | Another program (or another client) is using it | Close it; use a video file as the test source |
| Lines merged or split | A thread sent without the lock, or `recv` instead of `readline` | Always use `Connection.send` and `readline` |
