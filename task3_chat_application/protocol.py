"""Newline-delimited framing helpers shared by every chat script.

TCP is a byte stream: one recv() may return half a message or several messages at once.
LineReader buffers incoming bytes and hands back exactly one complete line at a time.
"""

from __future__ import annotations

import json
import socket
import threading
from typing import Any

MAX_LINE = 8192          # refuse absurdly long lines (protects the server's memory)
ENCODING = "utf-8"


class ProtocolError(Exception):
    """Raised when the peer sends data that breaks the framing rules."""


class LineReader:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._buffer = b""

    def read_line(self) -> str | None:
        """Return the next line (without newline) or None when the peer closed the connection."""
        while b"\n" not in self._buffer:
            if len(self._buffer) > MAX_LINE:
                raise ProtocolError("Line too long")
            chunk = self.sock.recv(4096)
            if not chunk:
                return None
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        if len(line) > MAX_LINE:
            raise ProtocolError("Line too long")
        return line.decode(ENCODING, errors="replace").rstrip("\r")


def send_line(sock: socket.socket, text: str, lock: threading.Lock | None = None) -> None:
    data = (text.replace("\n", " ") + "\n").encode(ENCODING)
    if lock is None:
        sock.sendall(data)
    else:
        with lock:                      # several threads may write to the same socket
            sock.sendall(data)


def send_json(sock: socket.socket, payload: dict[str, Any], lock: threading.Lock | None = None) -> None:
    send_line(sock, json.dumps(payload, ensure_ascii=False), lock)
