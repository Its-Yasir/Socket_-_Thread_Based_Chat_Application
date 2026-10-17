# -*- coding: utf-8 -*-
"""
gui.py  -  Tkinter desktop chat client (single file, stdlib only)

Protocol (server already built, do not change):
  Send:    LOGIN|name  MSG|room|text  PM|user|text  JOIN|room  LEAVE|room
  Receive: USERS|a,b,c  MSG|room|sender|text  PM|sender|text  INFO|text  ERROR|text
  Framing: each message is one UTF-8 line ending in "\\n"

Layout:
  One Tk window, two pages (LoginPage / MainPage) shown via grid raise.
  MainPage: three columns
    Left   – rooms list, join/leave controls, "Logged in as …" label
    Center – chat area (header + toolbar + scrollable messages + input bar)
    Right  – online-users list
"""

import queue
import socket
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import scrolledtext, simpledialog, messagebox
import time
import os

# ---------------------------------------------------------------------------
# Palette  (2 core colours + 1 accent + neutrals – no gradient slop)
# ---------------------------------------------------------------------------
CLR = {
    "bg":         "#1C1C1E",   # near-black canvas
    "surface":    "#2C2C2E",   # card / panel surface
    "surface2":   "#3A3A3C",   # raised element (input, header)
    "border":     "#48484A",   # subtle separator
    "accent":     "#0A84FF",   # Apple-blue – single focal point
    "accent_dim": "#0060C7",   # pressed / hover state of accent
    "fg":         "#F2F2F7",   # primary text
    "fg_dim":     "#8E8E93",   # secondary / placeholder text
    "error":      "#FF453A",   # error state
    "success":    "#30D158",   # online dot / success
    "pm_bg":      "#2D2233",   # private-message tint (distinct from room msgs)
}

FONT_FAMILY = "Segoe UI"       # clear reason: ships on all Windows installs,
                               # readable at small sizes, neutral enough to
                               # not fight the chat content

EMOJI_LIST = [
    "😊", "😂", "😍", "🙏", "👍", "❤️", "🔥", "😅",
    "🎉", "😎", "🤔", "👏", "😢", "🥰", "😜", "🤣",
]

# ---------------------------------------------------------------------------
# ChatClient  (no tkinter imports – pure network layer)
# ---------------------------------------------------------------------------

class ChatClient:
    """
    Opens a TCP connection to the chat server, sends framed lines, and
    receives lines in a background thread that deposits them into a queue.

    Public interface:
        .connect(host, port, timeout)  -> raises OSError on failure
        .send(line)                    -> thread-safe send
        .q                             -> queue.Queue of received lines
        .close()
    """

    def __init__(self):
        self.q: queue.Queue[str] = queue.Queue()
        self._sock: socket.socket | None = None
        self._file = None
        self._running = False
        self._send_lock = threading.Lock()

    # ------------------------------------------------------------------
    def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        """
        Connect with *timeout* seconds.  Raises OSError / socket.timeout
        on failure so the caller (LoginPage) can show the error.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))          # raises on failure
        sock.settimeout(None)               # blocking for the reader thread
        self._sock = sock
        self._file = sock.makefile("r", encoding="utf-8", errors="replace")
        self._running = True
        t = threading.Thread(target=self._reader, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    def send(self, line: str) -> None:
        """Send one protocol line (adds the trailing newline)."""
        if self._sock:
            try:
                with self._send_lock:
                    self._sock.sendall((line + "\n").encode("utf-8"))
            except OSError:
                pass   # connection already gone; reader will notice

    # ------------------------------------------------------------------
    def close(self) -> None:
        self._running = False
        try:
            if self._sock:
                self._sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------------
    def _reader(self) -> None:
        """Background thread: read lines and put them in the queue."""
        try:
            while self._running:
                line = self._file.readline()
                if not line:           # server closed connection
                    break
                self.q.put(line.rstrip("\n"))
        except OSError:
            pass
        finally:
            self.q.put("DISCONNECTED|")


# ---------------------------------------------------------------------------
# App  (controller: owns Tk root + ChatClient, drives the poll loop)
# ---------------------------------------------------------------------------

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Chat")
        self.root.configure(bg=CLR["bg"])
        self.root.minsize(900, 600)
        self.root.geometry("1080x680")

        self.client: ChatClient | None = None
        self.username: str = ""
        self.is_host: bool = False   # True only when user checks "I'm the host"

        # Container that holds both pages; each page fills the whole grid cell
        self._container = tk.Frame(self.root, bg=CLR["bg"])
        self._container.pack(fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        self.login_page = LoginPage(self._container, self)
        self.main_page  = MainPage(self._container, self)

        for page in (self.login_page, self.main_page):
            page.frame.grid(row=0, column=0, sticky="nsew")

        self._current_page: str = "login"
        self.show_login()
        self.root.after(100, self._poll)

    # ------------------------------------------------------------------
    def show_login(self):
        # Clean up any active call gracefully before going back to login
        try:
            import callManager
            callManager.on_peer_ended()
        except Exception:
            pass
        self.is_host = False
        self._current_page = "login"
        self.login_page.frame.tkraise()
        self.login_page.on_show()

    def show_main(self):
        self._current_page = "main"
        self.main_page.frame.tkraise()
        self.main_page.on_show()
        # Wire callManager callbacks so errors + status reach the GUI
        import callManager
        callManager.set_callbacks(
            on_error=lambda msg: self.root.after(
                0, lambda m=msg: self.main_page.handle_info(m, error=True)
            ),
            on_status_change=lambda active, peer: self.root.after(
                0, lambda a=active, p=peer: self.main_page.set_call_status(a, p)
            ),
        )

    # ------------------------------------------------------------------
    def _poll(self):
        """Drain the incoming queue safely without blocking the GUI event loop."""
        try:
            if self.client:
                count = 0
                while count < 50:
                    try:
                        line = self.client.q.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        self._dispatch(line)
                    except Exception as e:
                        print(f"[Error in dispatch] {e}")
                    count += 1
        finally:
            self.root.after(40, self._poll)

    # ------------------------------------------------------------------
    def _dispatch(self, line: str):
        parts = line.split("|")
        cmd   = parts[0] if parts else ""

        # Still on login page?
        if self._current_page == "login":
            if cmd == "USERS":
                # First USERS line means login succeeded
                self.login_page.on_login_ok()
                self.show_main()
                self.main_page.handle_users(parts[1] if len(parts) > 1 else "")
            elif cmd == "ERROR":
                msg = parts[1] if len(parts) > 1 else "Unknown error"
                self.login_page.show_error(msg)
                if self.client:
                    self.client.close()
                    self.client = None
            elif cmd == "DISCONNECTED":
                self.login_page.show_error("Connection closed by server.")
                self.client = None
            return

        # Main page dispatching
        if cmd == "USERS":
            self.main_page.handle_users(parts[1] if len(parts) > 1 else "")
        elif cmd == "MSG":
            room   = parts[1] if len(parts) > 1 else ""
            sender = parts[2] if len(parts) > 2 else ""
            text   = "|".join(parts[3:]) if len(parts) > 3 else ""
            self.main_page.handle_msg(room, sender, text)
        elif cmd == "PM":
            sender = parts[1] if len(parts) > 1 else ""
            text   = "|".join(parts[2:]) if len(parts) > 2 else ""
            self.main_page.handle_pm(sender, text)
        elif cmd == "INFO":
            self.main_page.handle_info("|".join(parts[1:]) if len(parts) > 1 else "")
        elif cmd == "ERROR":
            self.main_page.handle_info(
                "Error: " + (parts[1] if len(parts) > 1 else ""),
                error=True
            )
        elif cmd == "FILESTART":
            sender = parts[1] if len(parts) > 1 else ""
            tid = parts[2] if len(parts) > 2 else ""
            filename = parts[3] if len(parts) > 3 else ""
            size = parts[4] if len(parts) > 4 else "0"
            import fileReceive
            fileReceive.handle_file_start(sender, tid, filename, size, self.client)
            self.main_page.handle_info(f"Incoming file {filename} from {sender}...")
        elif cmd == "FILECHUNK":
            sender = parts[1] if len(parts) > 1 else ""
            tid = parts[2] if len(parts) > 2 else ""
            b64_data = parts[3] if len(parts) > 3 else ""
            import fileReceive
            fileReceive.handle_file_chunk(sender, tid, b64_data, self.client)
        elif cmd == "FILEEND":
            sender = parts[1] if len(parts) > 1 else ""
            tid = parts[2] if len(parts) > 2 else ""
            import fileReceive
            fileReceive.handle_file_end(sender, tid, self.client)
        elif cmd == "@FILESENT":
            target = parts[1] if len(parts) > 1 else ""
            filename = parts[2] if len(parts) > 2 else ""
            filepath = parts[3] if len(parts) > 3 else ""
            self.main_page.handle_file_sent(target, filename, filepath)
        elif cmd == "@FILERECEIVED":
            sender = parts[1] if len(parts) > 1 else ""
            filename = parts[2] if len(parts) > 2 else ""
            filepath = parts[3] if len(parts) > 3 else ""
            self.main_page.handle_file_received(sender, filename, filepath)
        elif cmd == "@FILEFAILED":
            tid = parts[1] if len(parts) > 1 else ""
            reason = parts[2] if len(parts) > 2 else ""
            self.main_page.handle_info(f"Upload failed: {reason}", error=True)
        elif cmd == "INCOMING":
            # INCOMING|caller|mode|ip|audioPort|videoPort
            caller = parts[1] if len(parts) > 1 else ""
            mode = parts[2] if len(parts) > 2 else "audio"
            ip = parts[3] if len(parts) > 3 else ""
            aport = parts[4] if len(parts) > 4 else "0"
            vport = parts[5] if len(parts) > 5 else "0"
            self.main_page.handle_incoming_call(caller, mode, ip, aport, vport)
        elif cmd == "ACCEPTED":
            # ACCEPTED|callee|ip|audioPort|videoPort
            callee = parts[1] if len(parts) > 1 else ""
            ip = parts[2] if len(parts) > 2 else ""
            aport = parts[3] if len(parts) > 3 else "0"
            vport = parts[4] if len(parts) > 4 else "0"
            import callManager
            callManager.handle_accepted(callee, ip, aport, vport)
            self.main_page.handle_info(f"Call with {callee} connected!")
        elif cmd == "REJECT":
            callee = parts[1] if len(parts) > 1 else ""
            reason = parts[2] if len(parts) > 2 else "declined"
            import callManager
            callManager.on_peer_ended()
            self.main_page.handle_info(f"Call rejected by {callee} ({reason})", error=True)
        elif cmd == "ENDCALL":
            other = parts[1] if len(parts) > 1 else ""
            import callManager
            callManager.on_peer_ended()
            self.main_page.handle_info(f"Call ended by {other}")
        elif cmd == "DISCONNECTED":
            self.main_page.handle_info("Disconnected from server.", error=True)
            self.client = None
            # Return to login after a short delay
            self.root.after(2000, self.show_login)

    # ------------------------------------------------------------------
    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _btn(parent, text, command, bg=None, fg=None, pad=(8, 4), **kw):
    """Flat styled button – no rounded pills, consistent radii via relief."""
    b = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg or CLR["accent"],
        fg=fg or CLR["fg"],
        activebackground=CLR["accent_dim"],
        activeforeground=CLR["fg"],
        relief="flat",
        cursor="hand2",
        padx=pad[0],
        pady=pad[1],
        bd=0,
        **kw,
    )
    return b


def _entry(parent, **kw):
    """Styled single-line entry."""
    return tk.Entry(
        parent,
        bg=CLR["surface2"],
        fg=CLR["fg"],
        insertbackground=CLR["fg"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightcolor=CLR["accent"],
        highlightbackground=CLR["border"],
        **kw,
    )


def _label(parent, text="", fg=None, font=None, **kw):
    return tk.Label(
        parent,
        text=text,
        bg=kw.pop("bg", CLR["bg"]),
        fg=fg or CLR["fg"],
        font=font,
        **kw,
    )


# ---------------------------------------------------------------------------
# LoginPage
# ---------------------------------------------------------------------------

class LoginPage:
    def __init__(self, container: tk.Frame, app: App):
        self.app = app
        self.frame = tk.Frame(container, bg=CLR["bg"])
        self._connect_timer: str | None = None   # root.after handle
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        f = self.frame

        # Centred card
        card = tk.Frame(f, bg=CLR["surface"], padx=36, pady=36)
        card.place(relx=0.5, rely=0.5, anchor="center")

        bold18 = tkfont.Font(family=FONT_FAMILY, size=18, weight="bold")
        norm11  = tkfont.Font(family=FONT_FAMILY, size=11)
        norm10  = tkfont.Font(family=FONT_FAMILY, size=10)

        _label(card, "Connect to Chat", font=bold18, bg=CLR["surface"],
               fg=CLR["fg"]).grid(row=0, column=0, columnspan=2,
                                   pady=(0, 24), sticky="w")

        # Username
        _label(card, "Username", font=norm10, bg=CLR["surface"],
               fg=CLR["fg_dim"]).grid(row=1, column=0, columnspan=2,
                                       sticky="w", pady=(0, 4))
        self._name_var = tk.StringVar()
        self._name_entry = _entry(card, textvariable=self._name_var,
                                  font=norm11, width=28)
        self._name_entry.grid(row=2, column=0, columnspan=2,
                              ipady=6, pady=(0, 14), sticky="ew")

        # Server IP
        _label(card, "Server IP", font=norm10, bg=CLR["surface"],
               fg=CLR["fg_dim"]).grid(row=3, column=0, columnspan=2,
                                       sticky="w", pady=(0, 4))
        self._ip_var = tk.StringVar(value="127.0.0.1")
        self._ip_entry = _entry(card, textvariable=self._ip_var,
                                font=norm11, width=28)
        self._ip_entry.grid(row=4, column=0, columnspan=2,
                            ipady=6, pady=(0, 20), sticky="ew")

        # Connect button
        self._connect_btn = _btn(card, "Connect", self._on_connect,
                                 font=norm11)
        self._connect_btn.grid(row=5, column=0, columnspan=2,
                               ipady=8, sticky="ew")

        # Error label  (hidden until needed)
        self._err_var = tk.StringVar()
        self._err_label = tk.Label(
            card,
            textvariable=self._err_var,
            bg=CLR["surface"],
            fg=CLR["error"],
            font=norm10,
            wraplength=280,
            justify="left",
        )
        self._err_label.grid(row=6, column=0, columnspan=2,
                             pady=(12, 0), sticky="w")
        self._err_label.grid_remove()   # hidden initially

        # Bind Enter key
        self._name_entry.bind("<Return>", lambda _: self._on_connect())
        self._ip_entry.bind("<Return>",   lambda _: self._on_connect())

    # ------------------------------------------------------------------
    def on_show(self):
        self._clear_error()
        self._connect_btn.config(state="normal", text="Connect")
        self._name_entry.focus_set()

    # ------------------------------------------------------------------
    def _on_connect(self):
        name = self._name_var.get().strip()
        ip   = self._ip_var.get().strip()

        if not name:
            self.show_error("Username cannot be empty.")
            return
        if not ip:
            self.show_error("Server IP cannot be empty.")
            return

        self._clear_error()
        self._connect_btn.config(state="disabled", text="Connecting…")

        # Connect in a thread so the GUI stays responsive
        def _do_connect():
            client = ChatClient()
            try:
                client.connect(ip, 5000, timeout=5.0)
            except (OSError, socket.timeout) as exc:
                self.app.root.after(0, lambda: self._connect_failed(str(exc)))
                return
            # Connection succeeded: store client, send LOGIN, wait for USERS
            self.app.client   = client
            self.app.username = name
            self.app.is_host  = True   # All users can make calls and record
            client.send(f"LOGIN|{name}")
            # Start a 3-second timeout in case no USERS arrives
            self.app.root.after(0, self._start_response_timeout)

        threading.Thread(target=_do_connect, daemon=True).start()

    # ------------------------------------------------------------------
    def _start_response_timeout(self):
        self._connect_timer = self.app.root.after(
            3000, self._on_response_timeout
        )

    def _on_response_timeout(self):
        if self.app._current_page == "login":
            # Still on login page after 3 s – server never replied with USERS
            if self.app.client:
                self.app.client.close()
                self.app.client = None
            self.show_error("Server did not respond in time. Try again.")
            self._connect_btn.config(state="normal", text="Connect")

    def on_login_ok(self):
        """Called by App._dispatch when first USERS line arrives."""
        if self._connect_timer:
            self.app.root.after_cancel(self._connect_timer)
            self._connect_timer = None

    # ------------------------------------------------------------------
    def _connect_failed(self, reason: str):
        self.show_error(f"Could not connect: {reason}")
        self._connect_btn.config(state="normal", text="Connect")

    def show_error(self, msg: str):
        self._err_var.set(msg)
        self._err_label.grid()

    def _clear_error(self):
        self._err_var.set("")
        self._err_label.grid_remove()


# ---------------------------------------------------------------------------
# MainPage
# ---------------------------------------------------------------------------

class MainPage:
    """
    Three-column layout using grid:
      col 0 – left panel  (rooms)
      col 1 – center      (chat)
      col 2 – right panel (users)
    """

    def __init__(self, container: tk.Frame, app: App):
        self.app = app
        self.frame = tk.Frame(container, bg=CLR["bg"])

        # State
        self._current_chat: str = ""   # room code or "@username" for PM
        self._rooms: list[str] = []
        self._users: list[str] = []
        # Per-conversation message history  { chat_key: [(tag, text), …] }
        self._history: dict[str, list[tuple[str, str]]] = {}

        self._build()
        self._voice_dialog = None
        self._video_dialog = None
        self._active_call_dlg = None

    # ------------------------------------------------------------------
    # BUILD
    # ------------------------------------------------------------------

    def _build(self):
        f = self.frame
        f.grid_columnconfigure(0, minsize=180, weight=0)
        f.grid_columnconfigure(1, weight=1)
        f.grid_columnconfigure(2, minsize=160, weight=0)
        f.grid_rowconfigure(0, weight=1)

        self._build_left(f)
        self._build_center(f)
        self._build_right(f)

    # ------ LEFT PANEL ------------------------------------------------

    def _build_left(self, parent):
        panel = tk.Frame(parent, bg=CLR["surface"], width=180)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        bold10 = tkfont.Font(family=FONT_FAMILY, size=10, weight="bold")
        norm10  = tkfont.Font(family=FONT_FAMILY, size=10)
        norm9   = tkfont.Font(family=FONT_FAMILY, size=9)

        # "Groups" header
        hdr = tk.Frame(panel, bg=CLR["surface"])
        hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(12, 4))
        _label(hdr, "GROUPS", font=bold10, bg=CLR["surface"],
               fg=CLR["fg_dim"]).pack(side="left")

        # Create Group button (prominent option 1)
        _btn(panel, "+ Create Group", self._on_create_group,
             font=norm9, pad=(6, 4)).grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 6))

        # Rooms/Groups listbox
        lb_frame = tk.Frame(panel, bg=CLR["surface"])
        lb_frame.grid(row=2, column=0, sticky="nsew", padx=8)
        lb_frame.grid_rowconfigure(0, weight=1)
        lb_frame.grid_columnconfigure(0, weight=1)

        self._rooms_lb = tk.Listbox(
            lb_frame,
            bg=CLR["surface"],
            fg=CLR["fg"],
            selectbackground=CLR["accent"],
            selectforeground=CLR["fg"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=norm10,
            activestyle="none",
        )
        self._rooms_lb.grid(row=0, column=0, sticky="nsew")
        self._rooms_lb.bind("<<ListboxSelect>>", self._on_room_select)

        sb = tk.Scrollbar(lb_frame, orient="vertical",
                          command=self._rooms_lb.yview,
                          bg=CLR["surface2"], troughcolor=CLR["surface"])
        sb.grid(row=0, column=1, sticky="ns")
        self._rooms_lb.config(yscrollcommand=sb.set)

        # Join by Room Code / Leave controls (option 2)
        ctrl = tk.Frame(panel, bg=CLR["surface"])
        ctrl.grid(row=3, column=0, sticky="ew", padx=8, pady=6)
        ctrl.grid_columnconfigure(0, weight=1)
        ctrl.grid_columnconfigure(1, weight=1)

        self._room_entry = _entry(ctrl, font=norm10, width=12)
        self._room_entry.grid(row=0, column=0, columnspan=2,
                              ipady=4, pady=(0, 4), sticky="ew")
        self._room_entry.insert(0, "Enter Room Code")
        self._room_entry.bind("<FocusIn>",  self._room_entry_focus_in)
        self._room_entry.bind("<FocusOut>", self._room_entry_focus_out)
        self._room_entry.bind("<Return>",   lambda _: self._on_join())

        _btn(ctrl, "Join Code",  self._on_join,  font=norm9,
             pad=(4, 3)).grid(row=1, column=0, sticky="ew", padx=(0, 2))
        _btn(ctrl, "Leave", self._on_leave,
             bg=CLR["surface2"], fg=CLR["fg_dim"],
             font=norm9, pad=(4, 3)).grid(row=1, column=1, sticky="ew",
                                          padx=(2, 0))

        # Copy Room Code button
        _btn(ctrl, "📋 Copy Code", self._on_copy_code,
             bg=CLR["surface2"], fg=CLR["fg"],
             font=norm9, pad=(4, 3)).grid(row=2, column=0, columnspan=2, sticky="ew",
                                          pady=(4, 0))

        # Separator
        sep = tk.Frame(panel, bg=CLR["border"], height=1)
        sep.grid(row=4, column=0, sticky="ew", padx=8, pady=4)

        # "Logged in as" label at the bottom
        self._login_label = _label(panel, "", font=norm9,
                                   bg=CLR["surface"], fg=CLR["fg_dim"])
        self._login_label.grid(row=5, column=0, sticky="w",
                               padx=10, pady=(0, 10))

    # ------ CENTER PANEL ----------------------------------------------

    def _build_center(self, parent):
        panel = tk.Frame(parent, bg=CLR["bg"])
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        bold12 = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")
        norm11  = tkfont.Font(family=FONT_FAMILY, size=11)
        norm10  = tkfont.Font(family=FONT_FAMILY, size=10)
        mono10  = tkfont.Font(family="Consolas",  size=10)

        # ----- Header bar
        header = tk.Frame(panel, bg=CLR["surface2"], pady=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_frame = tk.Frame(header, bg=CLR["surface2"])
        title_frame.grid(row=0, column=0, sticky="w", padx=14, pady=8)

        self._chat_title = _label(title_frame, "No Chat Selected", font=bold12,
                                  bg=CLR["surface2"], fg=CLR["fg"])
        self._chat_title.pack(side="left")

        self._header_copy_btn = _btn(title_frame, "📋 Copy Code", self._on_copy_code,
                                     bg=CLR["accent"], fg=CLR["fg"],
                                     font=norm10, pad=(6, 2))

        # Toolbar buttons: File, Voice, Video, Settings
        # Each button has a clear function – no dead controls (R-26)
        toolbar = tk.Frame(header, bg=CLR["surface2"])
        toolbar.grid(row=0, column=1, padx=8)

        toolbar_btns = [
            ("File",       self._on_file),
            ("Voice Rec",  self._on_voice),
            ("Video Rec",  self._on_video),
            ("Call Audio", self._on_call_audio),
            ("Call Video", self._on_call_video),
            ("End Call",   self._on_end_call),
            ("Folders",    self._on_open_folders),
            ("Settings",   self._on_settings),
        ]
        self._end_call_btn: tk.Button | None = None
        self._voice_btn = None
        for label_text, cmd in toolbar_btns:
            btn = _btn(toolbar, label_text, cmd,
                       bg=CLR["surface2"], fg=CLR["fg_dim"],
                       font=norm10, pad=(6, 4))
            btn.pack(side="left", padx=2, pady=4)
            if label_text == "End Call":
                self._end_call_btn = btn
            if label_text == "Voice":
                self._voice_btn = btn

        # ----- Call status bar (hidden until a call is active)
        self._call_bar = tk.Frame(header, bg=CLR["success"], pady=2)
        self._call_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._call_bar_label = tk.Label(
            self._call_bar,
            text="",
            bg=CLR["success"],
            fg="#FFFFFF",
            font=tkfont.Font(family=FONT_FAMILY, size=10, weight="bold"),
        )
        self._call_bar_label.pack(side="left", padx=12)
        self._call_bar.grid_remove()   # hidden initially

        # ----- Message area
        msg_frame = tk.Frame(panel, bg=CLR["bg"])
        msg_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        msg_frame.grid_rowconfigure(0, weight=1)
        msg_frame.grid_columnconfigure(0, weight=1)

        self._msg_text = tk.Text(
            msg_frame,
            bg=CLR["bg"],
            fg=CLR["fg"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=norm11,
            state="disabled",
            wrap="word",
            padx=14,
            pady=10,
            spacing3=4,
            cursor="arrow",
        )
        self._msg_text.grid(row=0, column=0, sticky="nsew")

        msg_sb = tk.Scrollbar(msg_frame, orient="vertical",
                              command=self._msg_text.yview,
                              bg=CLR["surface2"],
                              troughcolor=CLR["bg"])
        msg_sb.grid(row=0, column=1, sticky="ns")
        self._msg_text.config(yscrollcommand=msg_sb.set)

        # Text tags
        self._msg_text.tag_config("sender",
                                  foreground=CLR["accent"],
                                  font=tkfont.Font(family=FONT_FAMILY,
                                                   size=11, weight="bold"))
        self._msg_text.tag_config("body",   foreground=CLR["fg"])
        self._msg_text.tag_config("pm_bg",  background=CLR["pm_bg"])
        self._msg_text.tag_config("pm_sender",
                                  foreground="#BF5AF2",   # purple for PM
                                  font=tkfont.Font(family=FONT_FAMILY,
                                                   size=11, weight="bold"),
                                  background=CLR["pm_bg"])
        self._msg_text.tag_config("pm_body",
                                  foreground=CLR["fg"],
                                  background=CLR["pm_bg"])
        self._msg_text.tag_config("info",   foreground=CLR["fg_dim"],
                                  font=tkfont.Font(family=FONT_FAMILY,
                                                   size=10))
        self._msg_text.tag_config("error",  foreground=CLR["error"],
                                  font=tkfont.Font(family=FONT_FAMILY,
                                                   size=10))
        self._msg_text.tag_config("own",    foreground="#34C759")   # own echo

        # ----- Input bar
        input_bar = tk.Frame(panel, bg=CLR["surface2"])
        input_bar.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        input_bar.grid_columnconfigure(1, weight=1)

        # Emoji picker button
        self._emoji_btn = _btn(input_bar, "☺", self._toggle_emoji,
                               bg=CLR["surface2"], fg=CLR["fg_dim"],
                               font=tkfont.Font(family=FONT_FAMILY, size=13),
                               pad=(6, 6))
        self._emoji_btn.grid(row=0, column=0, padx=(8, 0), pady=8)

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(
            input_bar,
            textvariable=self._input_var,
            bg=CLR["surface"],
            fg=CLR["fg"],
            insertbackground=CLR["fg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightcolor=CLR["accent"],
            highlightbackground=CLR["surface2"],
            font=norm11,
        )
        self._input_entry.grid(row=0, column=1, ipady=7,
                               padx=8, pady=8, sticky="ew")
        self._input_entry.bind("<Return>", lambda _: self._on_send())

        self._send_btn = _btn(input_bar, "Send", self._on_send,
                              font=norm10, pad=(12, 6))
        self._send_btn.grid(row=0, column=2, padx=(0, 8), pady=8)

        # Emoji picker popup (hidden by default – functional toggle, R-26)
        self._emoji_popup: tk.Toplevel | None = None
        self._emoji_open = False

    # ------ RIGHT PANEL -----------------------------------------------

    def _build_right(self, parent):
        panel = tk.Frame(parent, bg=CLR["surface"], width=160)
        panel.grid(row=0, column=2, sticky="nsew")
        panel.grid_propagate(False)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        bold10 = tkfont.Font(family=FONT_FAMILY, size=10, weight="bold")
        norm10  = tkfont.Font(family=FONT_FAMILY, size=10)

        _label(panel, "ONLINE", font=bold10,
               bg=CLR["surface"], fg=CLR["fg_dim"]).grid(
            row=0, column=0, sticky="w", padx=10, pady=(12, 6))

        lb_frame = tk.Frame(panel, bg=CLR["surface"])
        lb_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        lb_frame.grid_rowconfigure(0, weight=1)
        lb_frame.grid_columnconfigure(0, weight=1)

        self._users_lb = tk.Listbox(
            lb_frame,
            bg=CLR["surface"],
            fg=CLR["fg"],
            selectbackground=CLR["accent"],
            selectforeground=CLR["fg"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=norm10,
            activestyle="none",
        )
        self._users_lb.grid(row=0, column=0, sticky="nsew")
        self._users_lb.bind("<Double-Button-1>", self._on_user_double_click)

        sb = tk.Scrollbar(lb_frame, orient="vertical",
                          command=self._users_lb.yview,
                          bg=CLR["surface2"], troughcolor=CLR["surface"])
        sb.grid(row=0, column=1, sticky="ns")
        self._users_lb.config(yscrollcommand=sb.set)

        norm9 = tkfont.Font(family=FONT_FAMILY, size=9)
        _label(panel, "Double-click to PM", font=norm9,
               bg=CLR["surface"], fg=CLR["fg_dim"]).grid(
            row=2, column=0, sticky="w", padx=10, pady=(0, 8))

    # ------------------------------------------------------------------
    # RESET (called on reconnect)
    # ------------------------------------------------------------------

    def reset_state(self):
        """Clear all runtime state so a reconnect starts fresh."""
        self._current_chat = ""
        self._rooms.clear()
        self._users.clear()
        self._history.clear()
        self._rooms_lb.delete(0, "end")
        self._users_lb.delete(0, "end")
        self._voice_dialog = None
        self._video_dialog = None
        if hasattr(self, "_active_call_dlg") and self._active_call_dlg:
            self._active_call_dlg.close()
            self._active_call_dlg = None
        # Hide call status bar
        if hasattr(self, "_call_bar"):
            self._call_bar.grid_remove()
        if self._end_call_btn:
            self._end_call_btn.config(bg=CLR["surface2"], fg=CLR["fg_dim"],
                                      text="End Call")

    def open_active_call_dialog(self, peer: str, mode: str, is_outgoing: bool):
        """Open or replace the floating Active Call window."""
        if hasattr(self, "_active_call_dlg") and self._active_call_dlg:
            self._active_call_dlg.close()
            self._active_call_dlg = None
        self._active_call_dlg = _ActiveCallDialog(self.app.root, self.app, peer, mode, is_outgoing)

    def set_call_status(self, active: bool, peer: str = ""):
        """
        Called by callManager (via App callback) when a call starts or ends.
        Shows/hides the green status bar and updates the Active Call window.
        """
        if active:
            self._call_bar_label.config(text=f"📞  Call active with {peer}")
            self._call_bar.grid()
            if self._end_call_btn:
                self._end_call_btn.config(bg=CLR["error"], fg="#FFFFFF",
                                          text=f"End Call ({peer})")
            if hasattr(self, "_active_call_dlg") and self._active_call_dlg:
                self._active_call_dlg.on_connected()
            elif peer:
                self.open_active_call_dialog(peer, "audio", is_outgoing=False)
        else:
            self._call_bar.grid_remove()
            if self._end_call_btn:
                self._end_call_btn.config(bg=CLR["surface2"], fg=CLR["fg_dim"],
                                          text="End Call")
            if hasattr(self, "_active_call_dlg") and self._active_call_dlg:
                self._active_call_dlg.close()
                self._active_call_dlg = None

    def on_show(self):
        self.reset_state()
        self._login_label.config(text=f"Logged in as {self.app.username}")
        self._switch_chat("")
        self._input_entry.focus_set()

    # ------------------------------------------------------------------
    # CHAT SWITCHING
    # ------------------------------------------------------------------

    def _switch_chat(self, chat_key: str):
        """Switch the center pane to a group or PM thread."""
        # Clear stale selections so listboxes stay consistent with the header
        self._rooms_lb.selection_clear(0, "end")
        self._users_lb.selection_clear(0, "end")
        self._current_chat = chat_key
        if not chat_key:
            self._chat_title.config(text="No Chat Selected")
            if hasattr(self, "_header_copy_btn"):
                self._header_copy_btn.pack_forget()
        elif chat_key.startswith("@"):
            self._chat_title.config(text=f"  {chat_key}")
            if hasattr(self, "_header_copy_btn"):
                self._header_copy_btn.pack_forget()
        else:
            self._chat_title.config(text=f"# {chat_key}")
            if hasattr(self, "_header_copy_btn"):
                self._header_copy_btn.pack(side="left", padx=(10, 0))
            # Keep rooms listbox in sync with the active room
            for i in range(self._rooms_lb.size()):
                if self._rooms_lb.get(i).strip() == chat_key:
                    self._rooms_lb.selection_set(i)
                    self._rooms_lb.see(i)
                    break
        self._reload_history()

    def _reload_history(self):
        """Re-render stored messages for the current chat."""
        self._msg_text.config(state="normal")
        self._msg_text.delete("1.0", "end")
        if not self._current_chat:
            welcome = (
                "  Welcome to Chat!\n\n"
                "  • Click '+ Create Group' on the left to create a private group with a Room Code.\n"
                "  • Enter a Room Code and click 'Join Code' to join a friend's group.\n"
                "  • Or double-click any online user on the right to start a private 1-to-1 chat.\n"
            )
            self._msg_text.insert("end", welcome, "info")
        else:
            for item in self._history.get(self._current_chat, []):
                if len(item) == 5 and item[0] == "file":
                    _, is_recv, peer, fname, fpath = item
                    self._append_file_card(is_recv, peer, fname, fpath)
                else:
                    tag_sender, tag_body, sender, body = item[:4]
                    self._append_raw(tag_sender, tag_body, sender, body)
        self._msg_text.config(state="disabled")
        self._msg_text.see("end")

    # ------------------------------------------------------------------
    # INCOMING MESSAGE HANDLERS
    # ------------------------------------------------------------------

    def handle_users(self, raw: str):
        names = [n.strip() for n in raw.split(",") if n.strip()]
        self._users.clear()
        self._users.extend(names)
        self._users_lb.delete(0, "end")
        for name in sorted(names):
            self._users_lb.insert("end", f"  {name}")

    def handle_msg(self, room: str, sender: str, text: str):
        # Ensure the room is known
        if room not in self._rooms:
            self._rooms.append(room)
            self._refresh_rooms_lb()
        key = room
        self._store_and_display(key, "sender", "body", sender, text)

    def handle_pm(self, sender: str, text: str):
        key = f"@{sender}"
        if key not in self._history:
            self._history[key] = []
        self._store_and_display(key, "pm_sender", "pm_body", f"PM from {sender}", text)

    def handle_info(self, text: str, error: bool = False):
        tag = "error" if error else "info"
        key = self._current_chat
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(("", tag, "", text))
        if self._current_chat == key:
            self._msg_text.config(state="normal")
            self._msg_text.insert("end", f"  {text}\n", tag)
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")

    def _store_and_display(self, key, tag_sender, tag_body, sender, body):
        if key not in self._history:
            self._history[key] = []
        self._history[key].append((tag_sender, tag_body, sender, body))
        if not self._current_chat:
            # Auto-open incoming conversation if user hasn't selected a chat yet
            self._switch_chat(key)
        elif self._current_chat == key:
            self._msg_text.config(state="normal")
            self._append_raw(tag_sender, tag_body, sender, body)
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")
        else:
            # User is in another chat: show a visible notification line
            self._msg_text.config(state="normal")
            self._msg_text.insert("end", f"  🔔 [Message from {key}]: {body}\n", "pm_sender" if key.startswith("@") else "info")
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")

    def _append_raw(self, tag_sender, tag_body, sender, body):
        if tag_sender == "" and tag_body in ("info", "error"):
            self._msg_text.insert("end", f"  {body}\n", tag_body)
        else:
            self._msg_text.insert("end", f"  {sender}: ", tag_sender)
            self._msg_text.insert("end", f"{body}\n", tag_body)

    def _open_file(self, filepath: str):
        if not filepath or not os.path.exists(filepath):
            messagebox.showwarning("File Not Found", f"Cannot find file:\n{filepath}", parent=self.app.root)
            return
        try:
            os.startfile(os.path.abspath(filepath))
        except Exception as e:
            messagebox.showerror("Error Opening File", f"Could not open file:\n{e}", parent=self.app.root)

    def _open_folder(self, filepath: str):
        full = os.path.abspath(filepath)
        folder = os.path.dirname(full) if os.path.isfile(full) else full
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        try:
            import subprocess
            if os.path.exists(full) and os.path.isfile(full):
                subprocess.Popen(f'explorer /select,"{full}"')
            else:
                os.startfile(folder)
        except Exception:
            try:
                os.startfile(folder)
            except Exception as e:
                messagebox.showerror("Error Opening Folder", f"Could not open folder:\n{e}", parent=self.app.root)

    def _append_file_card(self, is_received: bool, peer: str, filename: str, filepath: str):
        lower = filename.lower()
        if lower.endswith(".wav"):
            kind = "Voice Recording"
            icon = "🎙️"
            action_text = "▶ Play Audio"
        elif lower.endswith((".avi", ".mp4", ".mkv", ".mov")):
            kind = "Video Recording"
            icon = "📹"
            action_text = "▶ Watch Video"
        else:
            kind = "File"
            icon = "📁"
            action_text = "📄 Open File"

        direction = f"from {peer}" if is_received else f"sent to {peer}" if peer else "sent"

        self._link_counter = getattr(self, "_link_counter", 0) + 1
        t_open = f"link_open_{self._link_counter}"
        t_folder = f"link_folder_{self._link_counter}"

        self._msg_text.insert("end", f"  {icon} {kind} {direction}: ", "info")
        self._msg_text.insert("end", f"{filename}\n", "sender" if is_received else "own")
        self._msg_text.insert("end", "      ")
        self._msg_text.insert("end", f"[{action_text}]", t_open)
        self._msg_text.insert("end", "    ")
        self._msg_text.insert("end", "[📂 Open Folder]\n\n", t_folder)

        self._msg_text.tag_config(t_open, foreground=CLR["accent"], underline=True)
        self._msg_text.tag_bind(t_open, "<Button-1>", lambda e, p=filepath: self._open_file(p))
        self._msg_text.tag_bind(t_open, "<Enter>", lambda e: self._msg_text.config(cursor="hand2"))
        self._msg_text.tag_bind(t_open, "<Leave>", lambda e: self._msg_text.config(cursor="arrow"))

        self._msg_text.tag_config(t_folder, foreground=CLR["fg_dim"], underline=True)
        self._msg_text.tag_bind(t_folder, "<Button-1>", lambda e, p=filepath: self._open_folder(p))
        self._msg_text.tag_bind(t_folder, "<Enter>", lambda e: self._msg_text.config(cursor="hand2"))
        self._msg_text.tag_bind(t_folder, "<Leave>", lambda e: self._msg_text.config(cursor="arrow"))

    def handle_file_received(self, sender: str, filename: str, filepath: str):
        key = f"@{sender}" if (f"@{sender}" in self._history or not self._current_chat or self._current_chat.startswith("@")) else self._current_chat
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(("file", True, sender, filename, filepath))

        if not self._current_chat:
            self._switch_chat(key)
        elif self._current_chat == key:
            self._msg_text.config(state="normal")
            self._append_file_card(True, sender, filename, filepath)
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")
        else:
            self._msg_text.config(state="normal")
            self._append_file_card(True, sender, filename, filepath)
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")

    def handle_file_sent(self, target: str, filename: str, filepath: str):
        key = f"@{target}" if target and not target.startswith("@") and f"@{target}" in self._history else self._current_chat
        if not key:
            key = f"@{target}" if target else "General"
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(("file", False, target, filename, filepath))

        if self._current_chat == key or not self._current_chat:
            if not self._current_chat:
                self._switch_chat(key)
            else:
                self._msg_text.config(state="normal")
                self._append_file_card(False, target, filename, filepath)
                self._msg_text.config(state="disabled")
                self._msg_text.see("end")
        else:
            self._msg_text.config(state="normal")
            self._append_file_card(False, target, filename, filepath)
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")

    # ------------------------------------------------------------------
    # SEND
    # ------------------------------------------------------------------

    def _on_send(self):
        text = self._input_var.get().strip()
        if not text or not self.app.client:
            return
        if not self._current_chat:
            self.handle_info("Please select a group or user first to send messages.", error=True)
            return
        self._input_var.set("")

        if self._current_chat.startswith("@"):
            target = self._current_chat[1:]
            self.app.client.send(f"PM|{target}|{text}")
            # Echo own PM locally (server does not reflect it back)
            key = self._current_chat
            if key not in self._history:
                self._history[key] = []
            self._history[key].append(("own", "pm_body", f"You -> {target}", text))
            self._msg_text.config(state="normal")
            self._msg_text.insert("end", f"  You -> {target}: ", "own")
            self._msg_text.insert("end", f"{text}\n", "pm_body")
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")
        else:
            room = self._current_chat
            self.app.client.send(f"MSG|{room}|{text}")
            # Echo own room message locally
            key = room
            if key not in self._history:
                self._history[key] = []
            self._history[key].append(("own", "body", f"You", text))
            self._msg_text.config(state="normal")
            self._msg_text.insert("end", f"  You: ", "own")
            self._msg_text.insert("end", f"{text}\n", "body")
            self._msg_text.config(state="disabled")
            self._msg_text.see("end")

    # ------------------------------------------------------------------
    # GROUPS & ROOM CODE
    # ------------------------------------------------------------------

    def _on_create_group(self):
        import random, string
        name = simpledialog.askstring("Create Group", "Enter Group Name (e.g. StudyTeam):", parent=self.app.root)
        if not name:
            return
        name = name.strip().replace("|", "").replace(" ", "_")
        if not name:
            return
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        group_id = f"{name}-{code}"
        if self.app.client:
            self.app.client.send(f"JOIN|{group_id}")
        else:
            self.handle_info("Warning: Not connected – group created locally only.", error=True)
        if group_id not in self._rooms:
            self._rooms.append(group_id)
            self._refresh_rooms_lb()
        self._switch_chat(group_id)

        # Copy Room Code to clipboard automatically
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(group_id)
            self.app.root.update()
        except Exception:
            pass

        messagebox.showinfo(
            "Group Created",
            f"Group '{name}' created successfully!\n\nRoom Code: {group_id}\n\n(Code copied to clipboard! Share it with friends so they can join.)",
            parent=self.app.root
        )

    def _on_join(self):
        code = self._room_entry.get().strip()
        if not code or code == "Enter Room Code":
            messagebox.showwarning("Enter Code", "Please enter a Room Code to join.", parent=self.app.root)
            return
        if self.app.client:
            self.app.client.send(f"JOIN|{code}")
        else:
            self.handle_info("Warning: Not connected – joined locally only.", error=True)
        if code not in self._rooms:
            self._rooms.append(code)
            self._refresh_rooms_lb()
        self._switch_chat(code)
        self.handle_info(f"Joined group {code}")

    def _on_leave(self):
        room = self._current_chat
        if not room or room.startswith("@") or not self.app.client:
            return
        self.app.client.send(f"LEAVE|{room}")
        if room in self._rooms:
            self._rooms.remove(room)
            self._refresh_rooms_lb()
        self._switch_chat("")

    def _on_copy_code(self):
        room = self._current_chat
        if not room or room.startswith("@"):
            sel = self._rooms_lb.curselection()
            if sel:
                room = self._rooms_lb.get(sel[0]).strip()
            else:
                messagebox.showinfo("Copy Code", "Please select or open a group first to copy its code.", parent=self.app.root)
                return
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(room)
            self.app.root.update()
            messagebox.showinfo("Code Copied", f"Room Code copied to clipboard:\n\n{room}", parent=self.app.root)
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy: {e}", parent=self.app.root)

    def _on_room_select(self, _event=None):
        sel = self._rooms_lb.curselection()
        if sel:
            room = self._rooms_lb.get(sel[0]).strip()
            self._switch_chat(room)

    def _refresh_rooms_lb(self):
        self._rooms_lb.delete(0, "end")
        for r in self._rooms:
            self._rooms_lb.insert("end", f"  {r}")

    # ------------------------------------------------------------------
    # USERS
    # ------------------------------------------------------------------

    def _on_user_double_click(self, _event=None):
        sel = self._users_lb.curselection()
        if not sel:
            return
        name = self._users_lb.get(sel[0]).strip()
        if name == self.app.username:
            return     # can't PM yourself
        pm_key = f"@{name}"
        if pm_key not in self._history:
            self._history[pm_key] = []
        self._switch_chat(pm_key)

    # ------------------------------------------------------------------
    # EMOJI PICKER  (functional toggle, R-26)
    # ------------------------------------------------------------------

    def _toggle_emoji(self):
        if self._emoji_open and self._emoji_popup:
            self._emoji_popup.destroy()
            self._emoji_popup = None
            self._emoji_open  = False
            return

        self._emoji_open = True
        pop = tk.Toplevel(self.app.root)
        pop.overrideredirect(True)
        pop.config(bg=CLR["surface"])
        self._emoji_popup = pop

        # Position above the input bar
        bx = self._emoji_btn.winfo_rootx()
        by = self._emoji_btn.winfo_rooty()
        pop.geometry(f"+{bx}+{by - 170}")

        # Grid of emoji buttons
        cols = 4
        for i, em in enumerate(EMOJI_LIST):
            r, c = divmod(i, cols)
            b = tk.Button(
                pop,
                text=em,
                bg=CLR["surface"],
                activebackground=CLR["surface2"],
                relief="flat",
                bd=0,
                padx=6, pady=4,
                font=tkfont.Font(family=FONT_FAMILY, size=14),
                cursor="hand2",
                command=lambda e=em: self._insert_emoji(e),
            )
            b.grid(row=r, column=c, padx=2, pady=2)

        # Close when focus leaves
        pop.bind("<FocusOut>", lambda _: self._close_emoji_popup())
        pop.focus_set()

    def _insert_emoji(self, emoji: str):
        current = self._input_var.get()
        pos = int(self._input_entry.index(tk.INSERT))
        new_text = current[:pos] + emoji + current[pos:]
        self._input_var.set(new_text)
        self._input_entry.icursor(pos + len(emoji))
        self._close_emoji_popup()
        self._input_entry.focus_set()

    def _close_emoji_popup(self):
        if self._emoji_popup:
            self._emoji_popup.destroy()
            self._emoji_popup = None
            self._emoji_open  = False

    # ------------------------------------------------------------------
    # TOOLBAR BUTTONS  (each has a real action – R-26)
    # ------------------------------------------------------------------

    def _on_file(self):
        if not self.app.client:
            self.handle_info("Not connected.", error=True)
            return
        if not self._current_chat:
            self.handle_info("Select a group or user first before sending a file.", error=True)
            return
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(parent=self.app.root)
        if not filepath:
            return
        target = self._current_chat
        if target.startswith("@"):
            target = target[1:]
        import fileTransfer
        fileTransfer.send_file(self.app.client, target, filepath)
        self.handle_info(f"Uploading {os.path.basename(filepath)} to {self._current_chat}...")

    def _on_voice(self):
        if hasattr(self, "_voice_dialog") and self._voice_dialog and self._voice_dialog.dlg.winfo_exists():
            self._voice_dialog.dlg.lift()
            return
        self._voice_dialog = _VoiceDialog(self.app.root, self.app)

    def _on_video(self):
        if hasattr(self, "_video_dialog") and self._video_dialog and self._video_dialog.dlg.winfo_exists():
            self._video_dialog.dlg.lift()
            return
        self._video_dialog = _VideoDialog(self.app.root, self.app)

    def _get_call_target(self):
        if self._current_chat and self._current_chat.startswith("@"):
            return self._current_chat[1:]
        sel = self._users_lb.curselection()
        if sel:
            name = self._users_lb.get(sel[0]).strip()
            if name != self.app.username:
                return name
        return None

    def _on_call_audio(self):
        target = self._get_call_target()
        if not target:
            self.handle_info("Select or double-click a user on the right to start an audio call.", error=True)
            return
        if self.app.client:
            import callManager
            callManager.start_call(self.app.client, target, "audio")
            self.open_active_call_dialog(target, "audio", is_outgoing=True)
            self.handle_info(f"Calling {target} (Audio)...")
        else:
            self.handle_info("Not connected.", error=True)

    def _on_call_video(self):
        target = self._get_call_target()
        if not target:
            self.handle_info("Select or double-click a user on the right to start a video call.", error=True)
            return
        if self.app.client:
            import callManager
            callManager.start_call(self.app.client, target, "video")
            self.open_active_call_dialog(target, "video", is_outgoing=True)
            self.handle_info(f"Calling {target} (Video)...")
        else:
            self.handle_info("Not connected.", error=True)

    def _on_open_folders(self):
        """Open downloads or recordings folder in Windows File Explorer."""
        os.makedirs("downloads", exist_ok=True)
        os.makedirs("recordings", exist_ok=True)
        try:
            os.startfile(os.path.abspath("downloads"))
        except Exception as e:
            self.handle_info(f"Could not open folder: {e}", error=True)

    def _on_end_call(self):
        import callManager
        if hasattr(self, "_active_call_dlg") and self._active_call_dlg:
            self._active_call_dlg.close()
            self._active_call_dlg = None
        if not callManager.current_peer:
            self.handle_info("No active call to end.", error=True)
            return
        callManager.end_call(self.app.client)
        self.handle_info("Call ended.")

    def handle_incoming_call(self, caller, mode, ip, aport, vport):
        self.handle_info(f"🔔 INCOMING {mode.upper()} CALL from {caller}!")
        _IncomingCallDialog(self.app.root, self.app, caller, mode, ip, aport, vport)

    def _on_settings(self):
        _SettingsDialog(self.app.root, self.app)

    # ------------------------------------------------------------------
    # Room entry placeholder behaviour
    # ------------------------------------------------------------------

    def _room_entry_focus_in(self, _):
        if self._room_entry.get() == "Enter Room Code":
            self._room_entry.delete(0, "end")
            self._room_entry.config(fg=CLR["fg"])

    def _room_entry_focus_out(self, _):
        if not self._room_entry.get():
            self._room_entry.insert(0, "Enter Room Code")
            self._room_entry.config(fg=CLR["fg_dim"])


# ---------------------------------------------------------------------------
# Incoming Call dialog (prominent popup with Accept/Decline)
# ---------------------------------------------------------------------------

class _IncomingCallDialog:
    def __init__(self, parent, app: App, caller, mode, ip, aport, vport):
        self.app = app
        self.caller = caller
        self.mode = mode
        self.ip = ip
        self.aport = aport
        self.vport = vport
        self.answered = False

        self.dlg = tk.Toplevel(parent)
        self.dlg.title(f"Incoming {mode.upper()} Call")
        self.dlg.config(bg=CLR["surface"])
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.attributes("-topmost", True)
        self.dlg.lift()

        try:
            parent.bell()
        except Exception:
            pass

        bold13 = tkfont.Font(family=FONT_FAMILY, size=13, weight="bold")
        norm11 = tkfont.Font(family=FONT_FAMILY, size=11)

        icon = "📞" if mode == "audio" else "📹"
        tk.Label(self.dlg, text=f"{icon} Incoming {mode.upper()} Call", bg=CLR["surface"],
                 fg=CLR["accent"], font=bold13).pack(pady=(16, 4), padx=24)

        tk.Label(self.dlg, text=f"from {caller}", bg=CLR["surface"],
                 fg=CLR["fg"], font=norm11).pack(pady=(0, 16))

        btn_frame = tk.Frame(self.dlg, bg=CLR["surface"])
        btn_frame.pack(pady=(0, 20), padx=20)

        # Accept button (Green)
        accept_btn = tk.Button(
            btn_frame,
            text="✔ Accept Call",
            bg=CLR["success"],
            fg="#FFFFFF",
            activebackground="#28B84B",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=16, pady=8,
            font=bold13,
            cursor="hand2",
            command=self.accept,
        )
        accept_btn.grid(row=0, column=0, padx=8)

        # Decline button (Red)
        decline_btn = tk.Button(
            btn_frame,
            text="✖ Decline",
            bg=CLR["error"],
            fg="#FFFFFF",
            activebackground="#D63A30",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=16, pady=8,
            font=bold13,
            cursor="hand2",
            command=self.decline,
        )
        decline_btn.grid(row=0, column=1, padx=8)

        self.dlg.protocol("WM_DELETE_WINDOW", self.decline)

        self.dlg.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.dlg.winfo_width()
        dh = self.dlg.winfo_height()
        self.dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

    def accept(self):
        self.answered = True
        self.dlg.destroy()
        import callManager
        callManager.accept_call(self.app.client, self.caller, self.mode, self.ip, self.aport, self.vport)
        self.app.main_page.open_active_call_dialog(self.caller, self.mode, is_outgoing=False)
        self.app.main_page.handle_info(f"Accepted {self.mode} call from {self.caller}")

    def decline(self):
        if not self.answered:
            self.answered = True
            if self.app.client:
                self.app.client.send(f"REJECT|{self.caller}|declined")
            self.app.main_page.handle_info(f"Declined call from {self.caller}")
        try:
            self.dlg.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Active Call dialog (in-call window with live duration, mute, and end call)
# ---------------------------------------------------------------------------

class _ActiveCallDialog:
    def __init__(self, parent, app: App, peer: str, mode: str, is_outgoing: bool):
        self.app = app
        self.peer = peer
        self.mode = mode
        self.is_outgoing = is_outgoing
        self.seconds = 0
        self.is_muted = False
        self._timer_id = None
        self._destroyed = False

        self.dlg = tk.Toplevel(parent)
        self.dlg.title(f"{mode.capitalize()} Call - {peer}")
        self.dlg.config(bg=CLR["surface"])
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.attributes("-topmost", True)
        self.dlg.lift()

        bold14 = tkfont.Font(family=FONT_FAMILY, size=14, weight="bold")
        norm11  = tkfont.Font(family=FONT_FAMILY, size=11)
        bold11 = tkfont.Font(family=FONT_FAMILY, size=11, weight="bold")

        icon = "📞" if mode == "audio" else "📹"
        self._icon_lbl = tk.Label(
            self.dlg,
            text=f"{icon} {mode.upper()} CALL",
            bg=CLR["surface"],
            fg=CLR["accent"],
            font=bold14,
        )
        pad_top = 10 if mode == "video" else 18
        pad_stat = 8 if mode == "video" else 16
        pad_btn = 12 if mode == "video" else 20

        self._icon_lbl.pack(pady=(pad_top, 2), padx=28)

        self._peer_lbl = tk.Label(
            self.dlg,
            text=f"with {peer}",
            bg=CLR["surface"],
            fg=CLR["fg"],
            font=bold14,
        )
        self._peer_lbl.pack(pady=(0, 4))

        initial_status = "Calling... (Ringing)" if is_outgoing else "Connecting audio..."
        self._status_var = tk.StringVar(value=initial_status)
        self._status_lbl = tk.Label(
            self.dlg,
            textvariable=self._status_var,
            bg=CLR["surface"],
            fg=CLR["fg_dim"],
            font=norm11,
        )
        self._status_lbl.pack(pady=(0, pad_stat))

        btn_frame = tk.Frame(self.dlg, bg=CLR["surface"])
        btn_frame.pack(pady=(0, pad_btn), padx=16)

        # Mute Mic button
        self._mute_btn = tk.Button(
            btn_frame,
            text="🎙️ Mute",
            bg=CLR["surface2"],
            fg=CLR["fg"],
            activebackground=CLR["border"],
            activeforeground=CLR["fg"],
            relief="flat",
            bd=0,
            padx=14, pady=8,
            font=bold11,
            cursor="hand2",
            command=self.toggle_mute,
        )
        self._mute_btn.grid(row=0, column=0, padx=8)

        # End Call button
        end_btn = tk.Button(
            btn_frame,
            text="✖ End Call",
            bg=CLR["error"],
            fg="#FFFFFF",
            activebackground="#D63A30",
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=16, pady=8,
            font=bold11,
            cursor="hand2",
            command=self.on_end_click,
        )
        end_btn.grid(row=0, column=1, padx=8)

        self.dlg.protocol("WM_DELETE_WINDOW", self.on_end_click)

        # Position dialog: for video calls, move action dialog DOWN below camera windows
        self.dlg.update_idletasks()
        dw = self.dlg.winfo_width()
        dh = self.dlg.winfo_height()

        if mode == "video":
            sw = self.dlg.winfo_screenwidth()
            sh = self.dlg.winfo_screenheight()
            recv_w, recv_h = 640, 480
            send_w = 240
            gap = 16
            total_w = recv_w + gap + send_w
            start_x = max(20, (sw - total_w) // 2)
            cam_y = 20

            # Center action dialog directly under the large receiving window
            action_x = start_x + (recv_w - dw) // 2
            action_y = cam_y + recv_h + 38
            # Guard against taskbar overlap on compact screens
            if action_y + dh > sh - 35:
                action_y = max(cam_y, sh - dh - 45)
            self.dlg.geometry(f"+{action_x}+{action_y}")
        else:
            # Audio call: centre on parent window
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            self.dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

        if not is_outgoing:
            self.on_connected()

    def on_connected(self):
        if self._destroyed:
            return
        self._status_lbl.config(fg=CLR["success"])
        self._status_var.set("🟢 Connected (00:00)")
        if self._timer_id is None:
            self._tick()

    def _tick(self):
        if self._destroyed:
            return
        self.seconds += 1
        m, s = divmod(self.seconds, 60)
        self._status_var.set(f"🟢 Connected ({m:02d}:{s:02d})")
        self._timer_id = self.dlg.after(1000, self._tick)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        import audioCall
        audioCall.set_muted(self.is_muted)
        if self.is_muted:
            self._mute_btn.config(text="🔇 Unmute", bg=CLR["error"], fg="#FFFFFF")
        else:
            self._mute_btn.config(text="🎙️ Mute", bg=CLR["surface2"], fg=CLR["fg"])

    def on_end_click(self):
        self.app.main_page._on_end_call()
        self.close()

    def close(self):
        if self._destroyed:
            return
        self._destroyed = True
        if self._timer_id:
            try:
                self.dlg.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        try:
            self.dlg.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Voice dialog
# ---------------------------------------------------------------------------

class _VoiceDialog:
    def __init__(self, parent, app: App):
        self.app = app
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("Voice Recorder")
        self.dlg.config(bg=CLR["surface"])
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.focus_set()

        bold12 = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")
        norm11  = tkfont.Font(family=FONT_FAMILY, size=11)

        tk.Label(self.dlg, text="Voice Recorder", bg=CLR["surface"], fg=CLR["fg"], font=bold12).pack(pady=10)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.dlg, textvariable=self.status_var, bg=CLR["surface"], fg=CLR["fg_dim"]).pack(pady=5)

        btn_frame = tk.Frame(self.dlg, bg=CLR["surface"])
        btn_frame.pack(pady=10, padx=20)

        self.start_btn = _btn(btn_frame, "Start", self.start_rec, font=norm11)
        self.start_btn.grid(row=0, column=0, padx=4)

        self.stop_btn = _btn(btn_frame, "Stop", self.stop_rec, font=norm11, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=4)

        self.play_btn = _btn(btn_frame, "Play", self.play_rec, font=norm11, state="disabled")
        self.play_btn.grid(row=0, column=2, padx=4)

        self.send_btn = _btn(btn_frame, "Send to Chat", self.send_rec, font=norm11, state="disabled")
        self.send_btn.grid(row=0, column=3, padx=4)

        self.open_btn = _btn(btn_frame, "Open File", self.open_file, font=norm11, state="disabled")
        self.open_btn.grid(row=0, column=4, padx=4)

        _btn(btn_frame, "Folder", self.open_folder, font=norm11).grid(row=0, column=5, padx=4)

        _btn(btn_frame, "Exit", self.exit_dialog, font=norm11).grid(row=0, column=6, padx=4)

        self.filepath = None
        self.dlg.protocol("WM_DELETE_WINDOW", self.exit_dialog)

        # Centre on parent
        self.dlg.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.dlg.winfo_width()
        dh = self.dlg.winfo_height()
        self.dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

    def start_rec(self):
        import audioRecord
        ok = audioRecord.start()
        if not ok:
            self.status_var.set("Microphone not available!")
            return
        self.status_var.set("Recording...")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.play_btn.config(state="disabled")
        self.send_btn.config(state="disabled")
        self.open_btn.config(state="disabled")

    def stop_rec(self):
        import audioRecord
        self.filepath = audioRecord.stop()
        if self.filepath:
            self.status_var.set(f"Saved: {os.path.basename(self.filepath)}")
            self.play_btn.config(state="normal")
            self.send_btn.config(state="normal")
            self.open_btn.config(state="normal")
        else:
            self.status_var.set("No audio captured.")
            self.play_btn.config(state="disabled")
            self.send_btn.config(state="disabled")
            self.open_btn.config(state="disabled")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def open_file(self):
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.startfile(os.path.abspath(self.filepath))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}", parent=self.dlg)

    def open_folder(self):
        os.makedirs("recordings", exist_ok=True)
        try:
            os.startfile(os.path.abspath("recordings"))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open recordings folder:\n{e}", parent=self.dlg)

    def play_rec(self):
        if self.filepath:
            import audioRecord
            audioRecord.play_wav(self.filepath)
            self.status_var.set("Playing...")

    def send_rec(self):
        if not self.filepath:
            return
        target = self.app.main_page._current_chat
        if not target:
            messagebox.showwarning("No Chat Selected", "Please select a group or user first.", parent=self.dlg)
            return
        send_target = target[1:] if target.startswith("@") else target
        if self.app.client:
            import fileTransfer
            fileTransfer.send_file(self.app.client, send_target, self.filepath)
            self.app.main_page.handle_info(f"Sent voice recording to {target}")
            self.status_var.set(f"Sent to {target}!")
            self.send_btn.config(state="disabled")
        else:
            self.status_var.set("Not connected.")

    def exit_dialog(self):
        import audioRecord
        if audioRecord.is_recording:
            audioRecord.stop()
        self.dlg.destroy()


# ---------------------------------------------------------------------------
# Video dialog
# ---------------------------------------------------------------------------

class _VideoDialog:
    def __init__(self, parent, app: App):
        self.app = app
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("Video Recorder")
        self.dlg.config(bg=CLR["surface"])
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.focus_set()

        bold12 = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")
        norm11  = tkfont.Font(family=FONT_FAMILY, size=11)

        tk.Label(self.dlg, text="Video Recorder", bg=CLR["surface"], fg=CLR["fg"], font=bold12).pack(pady=10)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.dlg, textvariable=self.status_var, bg=CLR["surface"], fg=CLR["fg_dim"]).pack(pady=5)

        btn_frame = tk.Frame(self.dlg, bg=CLR["surface"])
        btn_frame.pack(pady=10, padx=20)

        self.start_btn = _btn(btn_frame, "Start", self.start_rec, font=norm11)
        self.start_btn.grid(row=0, column=0, padx=4)

        self.stop_btn = _btn(btn_frame, "Stop", self.stop_rec, font=norm11, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=4)

        self.play_btn = _btn(btn_frame, "Play", self.play_rec, font=norm11, state="disabled")
        self.play_btn.grid(row=0, column=2, padx=4)

        self.send_btn = _btn(btn_frame, "Send to Chat", self.send_rec, font=norm11, state="disabled")
        self.send_btn.grid(row=0, column=3, padx=4)

        self.open_btn = _btn(btn_frame, "Open File", self.open_file, font=norm11, state="disabled")
        self.open_btn.grid(row=0, column=4, padx=4)

        _btn(btn_frame, "Folder", self.open_folder, font=norm11).grid(row=0, column=5, padx=4)

        _btn(btn_frame, "Exit", self.exit_dialog, font=norm11).grid(row=0, column=6, padx=4)

        self.filepath = None
        self.dlg.protocol("WM_DELETE_WINDOW", self.exit_dialog)

        # Centre on parent
        self.dlg.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = self.dlg.winfo_width()
        dh = self.dlg.winfo_height()
        self.dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

    def start_rec(self):
        import videoRecord
        videoRecord.start()
        self.status_var.set("Recording...")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.play_btn.config(state="disabled")
        self.send_btn.config(state="disabled")
        self.open_btn.config(state="disabled")

    def stop_rec(self):
        import videoRecord
        self.filepath = videoRecord.stop()
        if self.filepath and os.path.exists(self.filepath):
            self.status_var.set(f"Saved: {os.path.basename(self.filepath)}")
            self.play_btn.config(state="normal")
            self.send_btn.config(state="normal")
            self.open_btn.config(state="normal")
        else:
            self.filepath = None
            self.status_var.set("No video captured.")
            self.play_btn.config(state="disabled")
            self.send_btn.config(state="disabled")
            self.open_btn.config(state="disabled")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    def open_file(self):
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.startfile(os.path.abspath(self.filepath))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n{e}", parent=self.dlg)

    def open_folder(self):
        os.makedirs("recordings", exist_ok=True)
        try:
            os.startfile(os.path.abspath("recordings"))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open recordings folder:\n{e}", parent=self.dlg)

    def play_rec(self):
        if self.filepath:
            import videoRecord
            videoRecord.play_video(self.filepath)
            self.status_var.set("Playing...")

    def send_rec(self):
        if not self.filepath:
            return
        target = self.app.main_page._current_chat
        if not target:
            messagebox.showwarning("No Chat Selected", "Please select a group or user first.", parent=self.dlg)
            return
        send_target = target[1:] if target.startswith("@") else target
        if self.app.client:
            import fileTransfer
            fileTransfer.send_file(self.app.client, send_target, self.filepath)
            self.app.main_page.handle_info(f"Sent video recording to {target}")
            self.status_var.set(f"Sent to {target}!")
            self.send_btn.config(state="disabled")
        else:
            self.status_var.set("Not connected.")

    def exit_dialog(self):
        import videoRecord
        if videoRecord.is_recording:
            videoRecord.stop()
        self.dlg.destroy()


# ---------------------------------------------------------------------------
# Settings dialog  (real dialog, closes with Escape – R-32)
# ---------------------------------------------------------------------------

class _SettingsDialog:
    def __init__(self, parent, app: App):
        self.app = app
        dlg = tk.Toplevel(parent)
        dlg.title("Settings")
        dlg.config(bg=CLR["surface"])
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()
        dlg.focus_set()

        bold12 = tkfont.Font(family=FONT_FAMILY, size=12, weight="bold")
        norm11  = tkfont.Font(family=FONT_FAMILY, size=11)
        norm10  = tkfont.Font(family=FONT_FAMILY, size=10)

        tk.Label(dlg, text="Settings", bg=CLR["surface"], fg=CLR["fg"],
                 font=bold12).pack(padx=24, pady=(20, 12))

        info = f"Username:  {app.username}\n"
        if app.client and app.client._sock:
            try:
                peer = app.client._sock.getpeername()
                info += f"Server:      {peer[0]}:{peer[1]}"
            except OSError:
                info += "Server:      disconnected"
        else:
            info += "Server:      disconnected"

        tk.Label(dlg, text=info, bg=CLR["surface"], fg=CLR["fg_dim"],
                 font=norm10, justify="left").pack(padx=24, pady=(0, 14),
                                                    anchor="w")

        btn_box = tk.Frame(dlg, bg=CLR["surface"])
        btn_box.pack(padx=24, pady=(0, 14), fill="x")

        def _open_dl():
            os.makedirs("downloads", exist_ok=True)
            try: os.startfile(os.path.abspath("downloads"))
            except: pass

        def _open_rec():
            os.makedirs("recordings", exist_ok=True)
            try: os.startfile(os.path.abspath("recordings"))
            except: pass

        _btn(btn_box, "📂 Open Downloads", _open_dl, font=norm10).pack(side="left", padx=(0, 4), expand=True, fill="x")
        _btn(btn_box, "🎙️ Open Recordings", _open_rec, font=norm10).pack(side="left", padx=(4, 0), expand=True, fill="x")

        _btn(dlg, "Close", dlg.destroy, font=norm11).pack(
            padx=24, pady=(0, 20), fill="x")

        # Keyboard close (R-32)
        dlg.bind("<Escape>", lambda _: dlg.destroy())

        # Centre on parent
        dlg.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = dlg.winfo_width()
        dh = dlg.winfo_height()
        dlg.geometry(f"+{px + (pw - dw)//2}+{py + (ph - dh)//2}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    App().run()
