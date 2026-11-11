"""Task 5 - Chat Application (Advanced tier): multi-room chat server.

Features
    * User registration and login (salted PBKDF2 password hashes in SQLite)
    * Multiple named chat rooms - join an existing room or create a new one
    * Message history per room, loaded when a user joins
    * One thread per client, JSON messages separated by newlines (see protocol.py)

Run:  python chat_server.py [--host 127.0.0.1] [--port 5050] [--db chat.db]

NOTE: traffic is NOT encrypted (plain TCP). See README.md "Security transparency".
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import secrets
import socket
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from protocol import LineReader, ProtocolError, send_json

DEFAULT_DB = Path(__file__).resolve().parent / "chat.db"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
ROOM_RE = re.compile(r"^[A-Za-z0-9_\-]{1,30}$")
MIN_PASSWORD = 6
MAX_PASSWORD = 128
MAX_MESSAGE = 1000
HISTORY_LIMIT = 50
MAX_LOGIN_FAILURES = 5
PBKDF2_ROUNDS = 200_000
DEFAULT_ROOM = "general"


class AuthError(Exception):
    pass


# ====================================================================== database
class ChatDatabase:
    """All persistent data: users (hashed passwords), rooms and message history."""

    def __init__(self, path: Path | str = DEFAULT_DB) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rooms (
                    name TEXT PRIMARY KEY COLLATE NOCASE,
                    created_by TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL COLLATE NOCASE,
                    username TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room, id);
                """
            )
            conn.execute("INSERT OR IGNORE INTO rooms (name, created_by, created_at) VALUES (?, NULL, ?)",
                         (DEFAULT_ROOM, _now()))

    @contextmanager
    def _connect(self):
        """Open a connection, commit on success / roll back on error, and always close it.

        (A bare `with sqlite3.connect(...)` only manages the transaction - it never closes
        the connection, which leaks file handles.)
        """
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ users
    @staticmethod
    def _hash(password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)

    def create_user(self, username: str, password: str) -> None:
        salt = secrets.token_bytes(16)
        digest = self._hash(password, salt)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO users (username, salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (username, salt, digest, _now()))
        except sqlite3.IntegrityError:
            raise AuthError("That username is already taken.") from None

    def verify_user(self, username: str, password: str) -> str | None:
        """Return the stored (canonical) username if the credentials are right, else None."""
        with self._connect() as conn:
            row = conn.execute("SELECT username, salt, password_hash FROM users WHERE username = ?",
                               (username,)).fetchone()
        if row is None:
            # Hash anyway so that unknown users and wrong passwords take similar time.
            self._hash(password, b"\x00" * 16)
            return None
        canonical, salt, stored = row
        return canonical if hmac.compare_digest(self._hash(password, salt), stored) else None

    # ------------------------------------------------------------------ rooms
    def ensure_room(self, name: str, created_by: str) -> str:
        """Create the room if needed and return its canonical name."""
        with self._lock, self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO rooms (name, created_by, created_at) VALUES (?, ?, ?)",
                         (name, created_by, _now()))
            return conn.execute("SELECT name FROM rooms WHERE name = ?", (name,)).fetchone()[0]

    def room_names(self) -> list[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute("SELECT name FROM rooms ORDER BY name COLLATE NOCASE")]

    # --------------------------------------------------------------- messages
    def add_message(self, room: str, username: str, text: str) -> str:
        sent_at = _now()
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO messages (room, username, text, sent_at) VALUES (?, ?, ?, ?)",
                         (room, username, text, sent_at))
        return sent_at

    def history(self, room: str, limit: int = HISTORY_LIMIT) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT username, text, sent_at FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?",
                (room, limit)).fetchall()
        return [{"user": u, "text": t, "ts": s} for u, t, s in reversed(rows)]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ======================================================================== server
class Session:
    """State for one connected client."""

    def __init__(self, sock: socket.socket, addr: tuple) -> None:
        self.sock = sock
        self.addr = addr
        self.reader = LineReader(sock)
        self.send_lock = threading.Lock()
        self.username: str | None = None
        self.room: str | None = None
        self.failed_logins = 0

    def send(self, payload: dict[str, Any]) -> None:
        send_json(self.sock, payload, self.send_lock)

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class ChatServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 5050, db_path: Path | str = DEFAULT_DB) -> None:
        self.host, self.port = host, port
        self.db = ChatDatabase(db_path)
        self._sock: socket.socket | None = None
        self._sessions: set[Session] = set()
        self._rooms: dict[str, set[Session]] = {}
        self._lock = threading.RLock()
        self._running = threading.Event()
        self._threads: set[threading.Thread] = set()

    # ------------------------------------------------------------- lifecycle
    def start(self) -> int:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(20)
        self.port = self._sock.getsockname()[1]
        self._running.set()
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self.port

    def shutdown(self) -> None:
        self._running.clear()
        if self._sock:
            self._sock.close()
        with self._lock:
            sessions = list(self._sessions)
            threads = list(self._threads)
        for session in sessions:
            session.close()
        for thread in threads:                      # let every client finish its clean-up
            if thread is not threading.current_thread():
                thread.join(timeout=2)

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                sock, addr = self._sock.accept()                  # type: ignore[union-attr]
            except OSError:
                break
            session = Session(sock, addr)
            thread = threading.Thread(target=self._serve, args=(session,), daemon=True)
            with self._lock:
                self._sessions.add(session)
                self._threads.add(thread)
            thread.start()

    # ---------------------------------------------------------- per-client loop
    def _serve(self, session: Session) -> None:
        try:
            while True:
                line = session.reader.read_line()
                if line is None:
                    break
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    session.send({"type": "error", "message": "Malformed message."})
                    continue
                if not isinstance(message, dict) or not isinstance(message.get("type"), str):
                    session.send({"type": "error", "message": "Malformed message."})
                    continue
                try:
                    keep_open = self._dispatch(session, message)
                except sqlite3.Error as exc:           # a DB problem must not kill the client thread
                    print(f"[server] database error: {exc}")
                    session.send({"type": "error",
                                  "message": "Server database error. Please try again."})
                    continue
                if not keep_open:
                    break
        except (OSError, ProtocolError):
            pass
        finally:
            self._disconnect(session)
            with self._lock:
                self._threads.discard(threading.current_thread())

    def _dispatch(self, session: Session, msg: dict[str, Any]) -> bool:
        """Handle one request. Returns False when the connection should be closed."""
        kind = msg["type"]

        if kind in ("register", "login"):
            return self._handle_auth(session, kind, msg)

        if session.username is None:
            session.send({"type": "error", "message": "Please log in first."})
            return True

        if kind == "join":
            self._handle_join(session, msg)
        elif kind == "message":
            self._handle_message(session, msg)
        elif kind == "rooms":
            session.send({"type": "rooms", "rooms": self._room_summary()})
        elif kind == "quit":
            return False
        else:
            session.send({"type": "error", "message": f"Unknown request '{kind[:30]}'."})
        return True

    # --------------------------------------------------------------- handlers
    def _handle_auth(self, session: Session, kind: str, msg: dict[str, Any]) -> bool:
        if session.username is not None:
            session.send({"type": "error", "message": "You are already logged in."})
            return True
        username, password = msg.get("username"), msg.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            session.send({"type": "error", "message": "Username and password are required."})
            return True

        if kind == "register":
            if not USERNAME_RE.match(username):
                session.send({"type": "error",
                              "message": "Username must be 3-20 letters, digits or underscores."})
                return True
            if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
                session.send({"type": "error",
                              "message": f"Password must be {MIN_PASSWORD}-{MAX_PASSWORD} characters."})
                return True
            try:
                self.db.create_user(username, password)
            except AuthError as err:
                session.send({"type": "error", "message": str(err)})
                return True
            session.send({"type": "registered", "username": username,
                          "message": "Account created. You can log in now."})
            return True

        # login
        canonical = self.db.verify_user(username, password) if len(password) <= MAX_PASSWORD else None
        if canonical is None:
            session.failed_logins += 1
            time.sleep(0.3)                                    # slows down password guessing
            session.send({"type": "error", "message": "Invalid username or password."})
            if session.failed_logins >= MAX_LOGIN_FAILURES:
                session.send({"type": "error", "message": "Too many failed attempts. Disconnecting."})
                return False
            return True
        with self._lock:
            if any(s.username and s.username.lower() == canonical.lower() for s in self._sessions):
                session.send({"type": "error", "message": "That account is already logged in."})
                return True
            session.username = canonical
        session.send({"type": "login_ok", "username": canonical, "rooms": self._room_summary()})
        return True

    def _handle_join(self, session: Session, msg: dict[str, Any]) -> None:
        room = msg.get("room")
        if not isinstance(room, str) or not ROOM_RE.match(room):
            session.send({"type": "error",
                          "message": "Room names use 1-30 letters, digits, '-' or '_'."})
            return
        room = self.db.ensure_room(room, session.username or "")
        if session.room and session.room.lower() == room.lower():
            session.send({"type": "error", "message": f"You are already in '{room}'."})
            return

        self._leave_room(session)
        with self._lock:
            self._rooms.setdefault(room.lower(), set()).add(session)
            session.room = room
            members = sorted(s.username for s in self._rooms[room.lower()] if s.username)
        session.send({"type": "joined", "room": room, "members": members,
                      "history": self.db.history(room)})
        self._broadcast(room, {"type": "system", "room": room,
                               "text": f"{session.username} joined the room."}, exclude=session)
        self._broadcast_rooms()

    def _handle_message(self, session: Session, msg: dict[str, Any]) -> None:
        if session.room is None:
            session.send({"type": "error", "message": "Join a room before sending messages."})
            return
        text = msg.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        text = text.strip()
        if len(text) > MAX_MESSAGE:
            session.send({"type": "error", "message": f"Messages are limited to {MAX_MESSAGE} characters."})
            return
        sent_at = self.db.add_message(session.room, session.username or "", text)
        self._broadcast(session.room, {"type": "message", "room": session.room,
                                       "user": session.username, "text": text, "ts": sent_at})

    # ----------------------------------------------------------- bookkeeping
    def _room_summary(self) -> list[dict[str, Any]]:
        with self._lock:
            counts = {name: len(members) for name, members in self._rooms.items()}
        return [{"name": n, "members": counts.get(n.lower(), 0)} for n in self.db.room_names()]

    def _broadcast(self, room: str, payload: dict[str, Any], exclude: Session | None = None) -> None:
        with self._lock:
            targets = [s for s in self._rooms.get(room.lower(), ()) if s is not exclude]
        for target in targets:
            try:
                target.send(payload)
            except OSError:
                target.close()

    def _broadcast_rooms(self) -> None:
        payload = {"type": "rooms", "rooms": self._room_summary()}
        with self._lock:
            targets = [s for s in self._sessions if s.username]
        for target in targets:
            try:
                target.send(payload)
            except OSError:
                target.close()

    def _leave_room(self, session: Session) -> None:
        with self._lock:
            room = session.room
            if room is None:
                return
            members = self._rooms.get(room.lower())
            if members:
                members.discard(session)
            session.room = None
        self._broadcast(room, {"type": "system", "room": room, "text": f"{session.username} left the room."})

    def _disconnect(self, session: Session) -> None:
        was_in_room = session.room is not None
        self._leave_room(session)
        with self._lock:
            self._sessions.discard(session)
        session.close()
        if was_in_room:
            try:
                self._broadcast_rooms()
            except sqlite3.Error as exc:               # clean-up must never raise
                print(f"[server] could not refresh the room list: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-room chat server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    server = ChatServer(args.host, args.port, args.db)
    try:
        port = server.start()
    except OSError as exc:
        print(f"Could not start the server on {args.host}:{args.port} - {exc}")
        return
    print(f"Chat server listening on {args.host}:{port}  (database: {args.db})  Ctrl+C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
