"""Network layer for the chat client (no GUI code), so it can be tested without a display."""

from __future__ import annotations

import json
import socket
import threading
from typing import Any, Callable

from protocol import LineReader, ProtocolError, send_json

EventHandler = Callable[[dict[str, Any]], None]


class ChatConnection:
    """Connects to the chat server and delivers every incoming event to `on_event`.

    `on_event` is called from a background thread. A final {"type": "disconnected"}
    event is delivered when the connection ends.
    """

    def __init__(self, host: str, port: int, on_event: EventHandler, timeout: float = 5.0) -> None:
        self.on_event = on_event
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def _receive_loop(self) -> None:
        reader = LineReader(self.sock)
        try:
            while True:
                line = reader.read_line()
                if line is None:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    self.on_event(event)
        except (OSError, ProtocolError):
            pass
        finally:
            self._closed.set()
            self.on_event({"type": "disconnected"})

    def send(self, payload: dict[str, Any]) -> bool:
        if self._closed.is_set():
            return False
        try:
            send_json(self.sock, payload, self._lock)
            return True
        except OSError:
            return False

    # Convenience wrappers ------------------------------------------------
    def register(self, username: str, password: str) -> bool:
        return self.send({"type": "register", "username": username, "password": password})

    def login(self, username: str, password: str) -> bool:
        return self.send({"type": "login", "username": username, "password": password})

    def join(self, room: str) -> bool:
        return self.send({"type": "join", "room": room})

    def say(self, text: str) -> bool:
        return self.send({"type": "message", "text": text})

    def request_rooms(self) -> bool:
        return self.send({"type": "rooms"})

    def close(self) -> None:
        self.send({"type": "quit"})
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
