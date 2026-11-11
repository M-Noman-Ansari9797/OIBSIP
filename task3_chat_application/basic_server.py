"""Task 5 - Chat Application (Beginner tier): two-user chat server using sockets + threading.

Run:  python basic_server.py [--host 127.0.0.1] [--port 5000]
"""

from __future__ import annotations

import argparse
import socket
import threading
from datetime import datetime

from protocol import LineReader, ProtocolError, send_line

MAX_NAME = 20
MAX_MESSAGE = 500


class BasicChatServer:
    MAX_CLIENTS = 2

    def __init__(self, host: str = "127.0.0.1", port: int = 5000) -> None:
        self.host, self.port = host, port
        self._sock: socket.socket | None = None
        self._clients: dict[socket.socket, str] = {}
        self._lock = threading.Lock()
        self._running = threading.Event()

    # ----------------------------------------------------------- lifecycle
    def start(self) -> int:
        """Bind, listen and accept clients in a background thread. Returns the port in use."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(5)
        self.port = self._sock.getsockname()[1]
        self._running.set()
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return self.port

    def shutdown(self) -> None:
        self._running.clear()
        if self._sock:
            self._sock.close()
        with self._lock:
            for conn in list(self._clients):
                try:
                    conn.close()
                except OSError:
                    pass
            self._clients.clear()

    def _accept_loop(self) -> None:
        while self._running.is_set():
            try:
                conn, _addr = self._sock.accept()          # type: ignore[union-attr]
            except OSError:
                break                                       # socket closed by shutdown()
            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    # ------------------------------------------------------------- clients
    def _handle_client(self, conn: socket.socket) -> None:
        reader = LineReader(conn)
        registered = False
        name = ""
        try:
            first = reader.read_line()
            if first is None:
                return
            name = first.strip()
            error, others = self._register(conn, name)
            if error:
                send_line(conn, f"*** {error} ***")
                return
            registered = True

            # `others` was captured atomically with the registration, so exactly one side
            # announces the other - never both, never a stale "joined" notice.
            if others:
                send_line(conn, f"*** Connected. {others[0][1]} is online - say hello! ***")
                for other_conn, _ in others:
                    try:
                        send_line(other_conn, f"*** {name} has joined the chat ***")
                    except OSError:
                        pass
            else:
                send_line(conn, "*** Connected. Waiting for the other user to join... ***")

            while True:
                line = reader.read_line()
                if line is None:
                    break
                text = line.strip()
                if not text:
                    continue
                if text.lower() == "/quit":
                    break
                stamp = datetime.now().strftime("%H:%M")
                self._broadcast(f"[{stamp}] {name}: {text[:MAX_MESSAGE]}")
        except (OSError, ProtocolError):
            pass
        finally:
            if registered:
                with self._lock:
                    self._clients.pop(conn, None)
                self._broadcast(f"*** {name} has left the chat ***")
            try:
                conn.close()
            except OSError:
                pass

    def _register(self, conn: socket.socket, name: str
                  ) -> tuple[str | None, list[tuple[socket.socket, str]]]:
        """Validate the name and add the client.

        Returns (error_message_or_None, clients_that_were_already_connected).
        """
        if not name:
            return "A name is required", []
        if len(name) > MAX_NAME or not name.isprintable():
            return f"Names must be 1-{MAX_NAME} printable characters", []
        with self._lock:
            if len(self._clients) >= self.MAX_CLIENTS:
                return "Chat is full (2 users maximum)", []
            if name.lower() in (n.lower() for n in self._clients.values()):
                return "That name is already taken", []
            others = list(self._clients.items())
            self._clients[conn] = name
        return None, others

    def _snapshot(self) -> list[tuple[socket.socket, str]]:
        with self._lock:
            return list(self._clients.items())

    def _broadcast(self, text: str, exclude: socket.socket | None = None) -> None:
        for conn, _name in self._snapshot():
            if conn is exclude:
                continue
            try:
                send_line(conn, text)
            except OSError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-user chat server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    server = BasicChatServer(args.host, args.port)
    try:
        port = server.start()
    except OSError as exc:
        print(f"Could not start the server on {args.host}:{args.port} - {exc}")
        return
    print(f"Chat server listening on {args.host}:{port}  (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
