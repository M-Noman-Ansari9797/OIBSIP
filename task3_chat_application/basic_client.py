"""Task 5 - Chat Application (Beginner tier): command-line client.

Run:  python basic_client.py [--host 127.0.0.1] [--port 5000] [--name Alice]
Type a message and press Enter. Type /quit to leave.
"""

from __future__ import annotations

import argparse
import socket
import threading

from protocol import LineReader, ProtocolError, send_line


def receive_loop(sock: socket.socket, stop: threading.Event) -> None:
    """Print everything the server sends until the connection closes."""
    reader = LineReader(sock)
    try:
        while not stop.is_set():
            line = reader.read_line()
            if line is None:
                break
            print(f"\r{line}\n> ", end="", flush=True)
    except (OSError, ProtocolError):
        pass
    if not stop.is_set():
        print("\r*** Connection closed. Press Enter to exit. ***")
    stop.set()


def run(host: str, port: int, name: str) -> None:
    try:
        sock = socket.create_connection((host, port), timeout=5)
    except OSError as exc:
        print(f"Could not connect to {host}:{port} - {exc}")
        return
    sock.settimeout(None)

    stop = threading.Event()
    send_line(sock, name)
    threading.Thread(target=receive_loop, args=(sock, stop), daemon=True).start()

    try:
        while not stop.is_set():
            try:
                message = input("> ")
            except EOFError:
                break
            if stop.is_set():
                break
            if not message.strip():
                continue
            send_line(sock, message)
            if message.strip().lower() == "/quit":
                break
    except (KeyboardInterrupt, OSError):
        pass
    finally:
        stop.set()
        try:
            sock.close()
        except OSError:
            pass
        print("\nYou left the chat.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Two-user chat client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--name", help="your display name")
    args = parser.parse_args()
    name = (args.name or input("Enter your name: ")).strip()
    if not name:
        print("A name is required.")
        return
    run(args.host, args.port, name)


if __name__ == "__main__":
    main()
