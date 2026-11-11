"""End-to-end tests for the chat applications.

They start real servers on random local ports and talk to them over real sockets and
real SQLite files, so no display, network access or manual setup is needed.
"""
import os
import queue
import re
import shutil
import socket
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing

from basic_server import BasicChatServer
from chat_client_lib import ChatConnection
from chat_server import ChatServer
from emoji_codes import render_emoji
from protocol import LineReader, send_line

TIMEOUT = 3.0


# ------------------------------------------------------------------ helpers
class RawClient:
    """Plain-text client for the Beginner server."""

    def __init__(self, port: int, name: str | None = None) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT)
        self.reader = LineReader(self.sock)
        if name is not None:
            send_line(self.sock, name)

    def send(self, text: str) -> None:
        send_line(self.sock, text)

    def read(self) -> str | None:
        return self.reader.read_line()

    def close(self) -> None:
        self.sock.close()


class EventClient:
    """Wraps ChatConnection and lets a test wait for a particular event type."""

    def __init__(self, port: int) -> None:
        self.events: queue.Queue = queue.Queue()
        self.conn = ChatConnection("127.0.0.1", port, self.events.put)

    def wait(self, kind: str, timeout: float = TIMEOUT) -> dict:
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise AssertionError(f"Timed out waiting for '{kind}' event")
            try:
                event = self.events.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError(f"Timed out waiting for '{kind}' event") from None
            if event.get("type") == kind:
                return event

    def expect_none(self, kind: str, wait: float = 0.6) -> None:
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                event = self.events.get(timeout=max(0.01, deadline - time.time()))
            except queue.Empty:
                return
            if event.get("type") == kind:
                raise AssertionError(f"Unexpected '{kind}' event: {event}")

    def close(self) -> None:
        self.conn.close()


# --------------------------------------------------------- Beginner tier tests
class BasicChatTests(unittest.TestCase):
    def setUp(self):
        self.server = BasicChatServer("127.0.0.1", 0)
        self.port = self.server.start()
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.server.shutdown()

    def connect(self, name):
        client = RawClient(self.port, name)
        self.clients.append(client)
        return client

    def test_two_users_exchange_timestamped_messages(self):
        alice = self.connect("Alice")
        self.assertIn("Waiting", alice.read())
        bob = self.connect("Bob")
        self.assertIn("Bob has joined", alice.read())
        self.assertIn("Alice is online", bob.read())

        alice.send("Hello")
        pattern = re.compile(r"^\[\d{2}:\d{2}\] Alice: Hello$")
        self.assertRegex(alice.read(), pattern)
        self.assertRegex(bob.read(), pattern)

        bob.send("Hi Alice!")
        self.assertRegex(alice.read(), r"^\[\d{2}:\d{2}\] Bob: Hi Alice!$")

    def test_disconnect_notifies_other_user(self):
        alice = self.connect("Alice")
        alice.read()
        bob = self.connect("Bob")
        alice.read()
        bob.read()
        bob.close()
        self.assertIn("Bob has left the chat", alice.read())

    def test_quit_command_leaves_chat(self):
        alice = self.connect("Alice")
        alice.read()
        bob = self.connect("Bob")
        alice.read()
        bob.read()
        bob.send("/quit")
        self.assertIn("Bob has left the chat", alice.read())

    def test_third_client_is_rejected(self):
        a, b = self.connect("Alice"), self.connect("Bob")
        a.read(); a.read(); b.read()
        carol = self.connect("Carol")
        self.assertIn("full", carol.read())

    def test_duplicate_name_is_rejected(self):
        self.connect("Alice").read()
        bob = self.connect("alice")
        self.assertIn("already taken", bob.read())

    def test_empty_name_is_rejected(self):
        client = self.connect("   ")
        self.assertIn("name is required", client.read())

    def test_message_split_across_packets_is_reassembled(self):
        alice = self.connect("Alice")
        alice.read()
        bob = self.connect("Bob")
        alice.read(); bob.read()
        alice.sock.sendall(b"Hel")
        time.sleep(0.2)
        alice.sock.sendall(b"lo\n")
        self.assertRegex(bob.read(), r"Alice: Hello$")

    def test_unicode_messages(self):
        alice = self.connect("Alice")
        alice.read()
        bob = self.connect("Bob")
        alice.read(); bob.read()
        alice.send("سلام 👋")
        self.assertIn("سلام 👋", bob.read())


# --------------------------------------------------------- Advanced tier tests
class AdvancedChatTests(unittest.TestCase):
    PASSWORD = "secret123"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "chat.db")
        self.server = ChatServer("127.0.0.1", 0, self.db_path)
        self.port = self.server.start()
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            try:
                c.close()
            except Exception:
                pass
        self.server.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def raw(self):
        client = EventClient(self.port)
        self.clients.append(client)
        return client

    def create_account(self, name):
        """Register an account without leaving a logged-in session behind."""
        client = self.raw()
        client.conn.register(name, self.PASSWORD)
        client.wait("registered")
        client.close()

    def user(self, name, room=None, register=True):
        client = self.raw()
        if register:
            client.conn.register(name, self.PASSWORD)
            client.wait("registered")
        client.conn.login(name, self.PASSWORD)
        client.wait("login_ok")
        if room:
            client.conn.join(room)
            client.wait("joined")
        return client

    # ---------------------------------------------------------- authentication
    def test_register_and_login(self):
        c = self.raw()
        c.conn.register("alice_1", self.PASSWORD)
        self.assertEqual(c.wait("registered")["username"], "alice_1")
        c.conn.login("alice_1", self.PASSWORD)
        event = c.wait("login_ok")
        self.assertEqual(event["username"], "alice_1")
        self.assertIn("general", [r["name"] for r in event["rooms"]])

    def test_duplicate_username_rejected_case_insensitively(self):
        self.user("Alice")
        c = self.raw()
        c.conn.register("alice", self.PASSWORD)
        self.assertIn("already taken", c.wait("error")["message"])

    def test_invalid_username_and_password_rejected(self):
        c = self.raw()
        c.conn.register("a b", self.PASSWORD)
        self.assertIn("Username", c.wait("error")["message"])
        c.conn.register("validname", "123")
        self.assertIn("Password", c.wait("error")["message"])
        c.conn.register("x'; DROP TABLE users;--", self.PASSWORD)
        self.assertIn("Username", c.wait("error")["message"])

    def test_wrong_password_rejected_then_correct_accepted(self):
        self.create_account("bob_smith")
        c = self.raw()
        c.conn.login("bob_smith", "wrongpass")
        self.assertIn("Invalid", c.wait("error")["message"])
        c.conn.login("nobody", self.PASSWORD)
        self.assertIn("Invalid", c.wait("error")["message"])
        c.conn.login("bob_smith", self.PASSWORD)
        c.wait("login_ok")

    def test_login_is_case_insensitive_and_returns_canonical_name(self):
        self.create_account("CarolX")
        c = self.raw()
        c.conn.login("carolx", self.PASSWORD)
        self.assertEqual(c.wait("login_ok")["username"], "CarolX")

    def test_password_is_hashed_not_stored_in_plain_text(self):
        self.user("dave_99")
        with closing(sqlite3.connect(self.db_path)) as conn:
            salt, digest = conn.execute("SELECT salt, password_hash FROM users").fetchone()
        self.assertEqual(len(salt), 16)
        self.assertEqual(len(digest), 32)
        with open(self.db_path, "rb") as f:
            self.assertNotIn(self.PASSWORD.encode(), f.read())

    def test_same_password_gets_different_hash_per_user(self):
        self.user("user_one")
        self.user("user_two")
        with closing(sqlite3.connect(self.db_path)) as conn:
            hashes = [r[0] for r in conn.execute("SELECT password_hash FROM users")]
        self.assertEqual(len(set(hashes)), 2)

    def test_duplicate_login_rejected(self):
        self.user("erin_22")
        c = self.raw()
        c.conn.login("erin_22", self.PASSWORD)
        self.assertIn("already logged in", c.wait("error")["message"])

    def test_must_log_in_before_anything_else(self):
        c = self.raw()
        c.conn.join("general")
        self.assertIn("log in", c.wait("error")["message"])
        c.conn.say("hi")
        self.assertIn("log in", c.wait("error")["message"])

    def test_repeated_failed_logins_disconnect(self):
        c = self.raw()
        for _ in range(5):
            c.conn.login("ghost", "badpass1")
        c.wait("disconnected", timeout=8)

    # -------------------------------------------------------------- rooms/chat
    def test_create_and_join_rooms_and_message_isolation(self):
        alice = self.user("alice_a", "alpha")
        bob = self.user("bob_b", "alpha")
        carol = self.user("carol_c", "beta")

        alice.conn.say("hello alpha")
        msg = bob.wait("message")
        self.assertEqual((msg["room"], msg["user"], msg["text"]), ("alpha", "alice_a", "hello alpha"))
        self.assertEqual(alice.wait("message")["text"], "hello alpha")   # sender gets an echo
        carol.expect_none("message")                                     # other room hears nothing

    def test_room_member_list_and_room_summary(self):
        self.user("alice_a", "alpha")
        bob = self.raw()
        bob.conn.register("bob_b", self.PASSWORD); bob.wait("registered")
        bob.conn.login("bob_b", self.PASSWORD); bob.wait("login_ok")
        bob.conn.join("alpha")
        joined = bob.wait("joined")
        self.assertEqual(joined["members"], ["alice_a", "bob_b"])
        bob.conn.request_rooms()
        rooms = {r["name"]: r["members"] for r in bob.wait("rooms")["rooms"]}
        self.assertEqual(rooms["alpha"], 2)

    def test_switching_rooms_notifies_old_room(self):
        alice = self.user("alice_a", "alpha")
        bob = self.user("bob_b", "alpha")
        alice.wait("system")                      # "bob_b joined the room."
        bob.conn.join("beta")
        bob.wait("joined")
        self.assertIn("left the room", alice.wait("system")["text"])

    def test_history_is_loaded_when_joining(self):
        alice = self.user("alice_a", "alpha")
        for i in range(3):
            alice.conn.say(f"message {i}")
            alice.wait("message")
        bob = self.raw()
        bob.conn.register("bob_b", self.PASSWORD); bob.wait("registered")
        bob.conn.login("bob_b", self.PASSWORD); bob.wait("login_ok")
        bob.conn.join("alpha")
        history = bob.wait("joined")["history"]
        self.assertEqual([h["text"] for h in history], ["message 0", "message 1", "message 2"])
        self.assertTrue(all(h["user"] == "alice_a" and h["ts"] for h in history))

    def test_history_limited_to_recent_messages(self):
        alice = self.user("alice_a", "alpha")
        for i in range(55):
            alice.conn.say(f"m{i}")
            alice.wait("message")
        bob = self.user("bob_b")
        bob.conn.join("alpha")
        history = bob.wait("joined")["history"]
        self.assertEqual(len(history), 50)
        self.assertEqual(history[-1]["text"], "m54")

    def test_history_survives_server_restart(self):
        alice = self.user("alice_a", "alpha")
        alice.conn.say("persist me")
        alice.wait("message")
        self.server.shutdown()

        self.server = ChatServer("127.0.0.1", 0, self.db_path)
        self.port = self.server.start()
        bob = self.user("alice_a", register=False)          # account also persisted
        bob.conn.join("alpha")
        self.assertEqual(bob.wait("joined")["history"][0]["text"], "persist me")

    def test_invalid_room_name_rejected(self):
        alice = self.user("alice_a")
        for bad in ("", "has space", "a" * 31, "../etc"):
            alice.conn.join(bad)
            self.assertIn("Room names", alice.wait("error")["message"])

    def test_message_before_joining_room_rejected(self):
        alice = self.user("alice_a")
        alice.conn.say("hi")
        self.assertIn("Join a room", alice.wait("error")["message"])

    def test_overlong_and_empty_messages(self):
        alice = self.user("alice_a", "alpha")
        alice.conn.say("x" * 1001)
        self.assertIn("limited", alice.wait("error")["message"])
        alice.conn.say("   ")
        alice.expect_none("message")

    def test_sql_injection_text_is_stored_literally(self):
        alice = self.user("alice_a", "alpha")
        evil = "'); DROP TABLE messages;--"
        alice.conn.say(evil)
        alice.wait("message")
        with closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT text FROM messages").fetchone()[0], evil)

    def test_disconnect_is_announced_to_room(self):
        alice = self.user("alice_a", "alpha")
        bob = self.user("bob_b", "alpha")
        alice.wait("system")
        bob.close()
        self.assertIn("bob_b left", alice.wait("system")["text"])

    # ------------------------------------------------------------ robustness
    def test_malformed_json_gets_error_and_connection_survives(self):
        c = self.raw()
        c.conn.sock.sendall(b"this is not json\n")
        self.assertIn("Malformed", c.wait("error")["message"])
        c.conn.sock.sendall(b"[1,2,3]\n")
        self.assertIn("Malformed", c.wait("error")["message"])
        c.conn.register("still_alive", self.PASSWORD)
        c.wait("registered")

    def test_unknown_request_type(self):
        alice = self.user("alice_a")
        alice.conn.send({"type": "hack"})
        self.assertIn("Unknown", alice.wait("error")["message"])

    def test_oversized_line_drops_connection(self):
        c = self.raw()
        try:
            c.conn.sock.sendall(b"A" * 20000)
        except OSError:
            pass
        c.wait("disconnected")


class EmojiTests(unittest.TestCase):
    def test_known_shortcodes(self):
        self.assertEqual(render_emoji("hi :smile:"), "hi \U0001F604")
        self.assertEqual(render_emoji(":thumbsup: :heart:"), "\U0001F44D ❤️")

    def test_unknown_and_plain_text_untouched(self):
        self.assertEqual(render_emoji("ratio 3:4 and :notacode:"), "ratio 3:4 and :notacode:")
        self.assertEqual(render_emoji("12:30:45"), "12:30:45")

    def test_case_insensitive(self):
        self.assertEqual(render_emoji(":SMILE:"), "\U0001F604")


if __name__ == "__main__":
    unittest.main()
