"""Task 5 - Chat Application (Advanced tier): tkinter chat client.

Features: login/registration, multiple rooms, message history on join, emoji shortcodes,
and notifications (bell + title badge + optional desktop pop-up) when the window is not focused.

Run:  python chat_gui.py      (start chat_server.py first)
"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import ttk

from chat_client_lib import ChatConnection
from emoji_codes import render_emoji

try:                                  # optional: native desktop notifications
    from plyer import notification as desktop_notification
except Exception:                      # pragma: no cover - plyer is not required
    desktop_notification = None

APP_TITLE = "Python Chat"
DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", "5050"


class ChatApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("860x600")
        self.minsize(700, 480)

        self.events: queue.Queue = queue.Queue()
        self.conn: ChatConnection | None = None
        self.username = ""
        self.current_room = ""
        self.unread = 0

        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        self.port_var = tk.StringVar(value=DEFAULT_PORT)
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.login_status = tk.StringVar()
        self.chat_status = tk.StringVar()
        self.room_var = tk.StringVar()
        self.msg_var = tk.StringVar()

        self.login_frame = ttk.Frame(self, padding=30)
        self.chat_frame = ttk.Frame(self, padding=8)
        self._build_login()
        self._build_chat()
        self.login_frame.pack(fill="both", expand=True)

        self.bind("<FocusIn>", self._on_focus)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_events)

    # ------------------------------------------------------------------- UI
    def _build_login(self) -> None:
        f = self.login_frame
        f.columnconfigure(1, weight=1)
        ttk.Label(f, text="Welcome to Python Chat", font=("Segoe UI", 18, "bold")
                  ).grid(row=0, column=0, columnspan=2, pady=(0, 18))
        rows = [("Server", self.host_var, ""), ("Port", self.port_var, ""),
                ("Username", self.user_var, ""), ("Password", self.pass_var, "*")]
        for i, (label, var, show) in enumerate(rows, start=1):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=5)
            entry = ttk.Entry(f, textvariable=var, show=show, width=32)
            entry.grid(row=i, column=1, sticky="ew", pady=5, padx=(12, 0))
            if label == "Password":
                entry.bind("<Return>", lambda _e: self.login())
        buttons = ttk.Frame(f)
        buttons.grid(row=5, column=0, columnspan=2, pady=14)
        ttk.Button(buttons, text="Login", command=self.login).pack(side="left", padx=6)
        ttk.Button(buttons, text="Register", command=self.register).pack(side="left", padx=6)
        self.login_msg = ttk.Label(f, textvariable=self.login_status, wraplength=420, foreground="#c0392b")
        self.login_msg.grid(row=6, column=0, columnspan=2)
        ttk.Label(f, text="Note: messages are sent unencrypted. Do not reuse a real password.",
                  foreground="#7f8c8d").grid(row=7, column=0, columnspan=2, pady=(18, 0))

    def _build_chat(self) -> None:
        f = self.chat_frame
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)

        side = ttk.LabelFrame(f, text="Rooms", padding=6)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self.room_list = tk.Listbox(side, width=22, exportselection=False, activestyle="none")
        self.room_list.pack(fill="both", expand=True)
        self.room_list.bind("<Double-Button-1>", self._join_selected)
        ttk.Label(side, text="Create or join:").pack(anchor="w", pady=(8, 2))
        room_entry = ttk.Entry(side, textvariable=self.room_var)
        room_entry.pack(fill="x")
        room_entry.bind("<Return>", lambda _e: self.join_typed())
        ttk.Button(side, text="Create / Join", command=self.join_typed).pack(fill="x", pady=4)
        ttk.Button(side, text="Log out", command=self.logout).pack(fill="x", pady=(14, 0))

        main = ttk.Frame(f)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        self.text = tk.Text(main, state="disabled", wrap="word", font=("Segoe UI", 11), padx=8, pady=8)
        scrollbar = ttk.Scrollbar(main, command=self.text.yview)
        self.text.config(yscrollcommand=scrollbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text.tag_configure("me", foreground="#1a5fb4")
        self.text.tag_configure("other", foreground="#111111")
        self.text.tag_configure("system", foreground="#7f8c8d", font=("Segoe UI", 10, "italic"))
        self.text.tag_configure("error", foreground="#c0392b", font=("Segoe UI", 10, "bold"))
        self.text.tag_configure("history", foreground="#5d6d7e")

        bottom = ttk.Frame(main)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        self.msg_entry = ttk.Entry(bottom, textvariable=self.msg_var, font=("Segoe UI", 11))
        self.msg_entry.grid(row=0, column=0, sticky="ew")
        self.msg_entry.bind("<Return>", lambda _e: self.send_message())
        ttk.Button(bottom, text="Send", command=self.send_message).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(main, textvariable=self.chat_status, foreground="#7f8c8d"
                  ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # ------------------------------------------------------------ connection
    def _connect(self) -> bool:
        self.login_status.set("")
        host = self.host_var.get().strip() or DEFAULT_HOST
        try:
            port = int(self.port_var.get())
        except ValueError:
            self.login_status.set("Port must be a number.")
            return False
        if not self.user_var.get().strip() or not self.pass_var.get():
            self.login_status.set("Enter a username and password.")
            return False
        if self.conn is None:
            try:
                self.conn = ChatConnection(host, port, self.events.put)
            except OSError as exc:
                self.login_status.set(f"Could not connect to {host}:{port} - {exc}")
                self.conn = None
                return False
        return True

    def login(self) -> None:
        if self._connect() and self.conn:
            self.conn.login(self.user_var.get().strip(), self.pass_var.get())

    def register(self) -> None:
        if self._connect() and self.conn:
            self.conn.register(self.user_var.get().strip(), self.pass_var.get())

    def logout(self) -> None:
        self._drop_connection()
        self._show_login("Logged out.")

    def _drop_connection(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
        while not self.events.empty():       # discard stale events from the old connection
            self.events.get_nowait()

    def _on_close(self) -> None:
        self._drop_connection()
        self.destroy()

    # --------------------------------------------------------------- actions
    def join_typed(self) -> None:
        room = self.room_var.get().strip()
        if room and self.conn:
            self.conn.join(room)
            self.room_var.set("")

    def _join_selected(self, _event: tk.Event) -> None:
        selection = self.room_list.curselection()
        if selection and self.conn:
            name = self.room_list.get(selection[0]).rsplit(" (", 1)[0]
            self.conn.join(name)

    def send_message(self) -> None:
        text = self.msg_var.get().strip()
        if not text or not self.conn:
            return
        if not self.current_room:
            self._append("Join a room first (double-click one on the left).", "error")
            return
        self.conn.say(text)
        self.msg_var.set("")

    # ---------------------------------------------------------------- events
    def _poll_events(self) -> None:
        try:
            while True:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _handle(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "login_ok":
            self.username = event["username"]
            self.pass_var.set("")
            self._show_chat()
            self._update_rooms(event.get("rooms", []))
            self.conn and self.conn.join("general")
        elif kind == "registered":
            self.login_msg.config(foreground="#27ae60")
            self.login_status.set(event.get("message", "Account created."))
        elif kind == "joined":
            self._on_joined(event)
        elif kind == "message":
            self._on_message(event)
        elif kind == "system":
            if event.get("room") == self.current_room:
                self._append(event.get("text", ""), "system")
        elif kind == "rooms":
            self._update_rooms(event.get("rooms", []))
        elif kind == "error":
            self._on_error(event.get("message", "Unknown error."))
        elif kind == "disconnected":
            if self.conn is not None:
                self.conn = None
                self._show_login("Connection to the server was lost.")

    def _on_error(self, message: str) -> None:
        if self.chat_frame.winfo_ismapped():
            self._append(message, "error")
        else:
            self.login_msg.config(foreground="#c0392b")
            self.login_status.set(message)

    def _on_joined(self, event: dict) -> None:
        self.current_room = event["room"]
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        history = event.get("history", [])
        if history:
            self._append(f"--- last {len(history)} messages in #{self.current_room} ---", "system")
            for item in history:
                self._append(self._format(item), "history")
            self._append("--- end of history ---", "system")
        else:
            self._append(f"Welcome to #{self.current_room}. No messages yet - say hello!", "system")
        self.chat_status.set(f"#{self.current_room}  |  online: {', '.join(event.get('members', []))}  "
                             f"|  signed in as {self.username}")
        self.msg_entry.focus_set()

    def _on_message(self, event: dict) -> None:
        if event.get("room") != self.current_room:
            return
        mine = event.get("user") == self.username
        self._append(self._format(event), "me" if mine else "other")
        if not mine and self.focus_displayof() is None:        # window is not focused
            self._notify(event.get("user", "?"), render_emoji(event.get("text", "")))

    # ----------------------------------------------------------- helpers/UI
    @staticmethod
    def _format(item: dict) -> str:
        stamp = str(item.get("ts", ""))[11:16] or "--:--"
        return f"[{stamp}] {item.get('user', '?')}: {render_emoji(item.get('text', ''))}"

    def _append(self, line: str, tag: str) -> None:
        self.text.config(state="normal")
        self.text.insert("end", line + "\n", tag)
        self.text.config(state="disabled")
        self.text.see("end")

    def _update_rooms(self, rooms: list[dict]) -> None:
        self.room_list.delete(0, "end")
        for room in rooms:
            self.room_list.insert("end", f"{room['name']} ({room['members']})")
            if room["name"] == self.current_room:
                self.room_list.selection_set("end")

    def _notify(self, user: str, text: str) -> None:
        self.unread += 1
        self.title(f"({self.unread}) New message - {APP_TITLE}")
        self.bell()
        if desktop_notification is not None:
            try:
                desktop_notification.notify(title=f"{user} in #{self.current_room}",
                                            message=text[:120], timeout=4)
            except Exception:
                pass

    def _on_focus(self, _event: tk.Event) -> None:
        if self.unread:
            self.unread = 0
            self.title(APP_TITLE)

    def _show_chat(self) -> None:
        self.login_frame.pack_forget()
        self.chat_frame.pack(fill="both", expand=True)

    def _show_login(self, message: str) -> None:
        self.chat_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)
        self.current_room = ""
        self.login_msg.config(foreground="#c0392b")
        self.login_status.set(message)
        self.title(APP_TITLE)


if __name__ == "__main__":
    ChatApp().mainloop()
