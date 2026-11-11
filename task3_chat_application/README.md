# Task 5 – Chat Application (Python)

A real-time chat system built on raw TCP sockets and threads. Both tiers are included:
a **two-user command-line chat** (Beginner) and a **multi-room chat with accounts, history and a
tkinter GUI** (Advanced).

## Features

### Beginner tier – `basic_server.py` + `basic_client.py`
| Requirement | Implementation |
|---|---|
| Server that listens for connections | `BasicChatServer` (`socket`, one `threading.Thread` per client) |
| Client that connects to the server | `basic_client.py` |
| Real-time two-way messaging | Server relays each message to both users |
| Timestamp prefix `[14:35] Alice: Hello` | Added by the server (`%H:%M`) |
| Graceful disconnect notification | `*** Bob has left the chat ***` (also on `/quit` or a dropped connection) |
| Runs on one machine | Defaults to `127.0.0.1:5000` |

Extras: a third user is refused ("chat is full"), duplicate or empty names are rejected, and
messages split across TCP packets are reassembled correctly.

### Advanced tier – `chat_server.py` + `chat_gui.py`
| Requirement | Implementation |
|---|---|
| GUI chat window | tkinter client (`chat_gui.py`) |
| Registration & login (SQLite) | Salted **PBKDF2-HMAC-SHA256** hashes (200,000 rounds) in `chat.db` |
| Multiple rooms, create or join | Type a name in "Create / Join" or double-click a room; `general` exists by default |
| Message history on join | Last 50 messages of the room are sent when you join |
| Notifications when not focused | System bell + `(n) New message` title badge; native pop-up too if `plyer` is installed |
| Emoji shortcodes | `:smile:` → 😄 (about 50 codes in `emoji_codes.py`); also applied to history |
| Security transparency | See the section below |

Server hardening: usernames/rooms validated with strict patterns, 1000-char message limit,
8 KB line limit, parameterised SQL only, one active login per account, login delay and
disconnect after 5 failed attempts, and database errors reported as clean errors instead of crashing.

## Setup & run

No third-party packages are required (standard library only). `plyer` is optional.

```bash
# Beginner tier - open three terminals
python basic_server.py
python basic_client.py --name Alice
python basic_client.py --name Bob          # type a message and press Enter; /quit to leave

# Advanced tier
python chat_server.py                      # terminal 1 (creates chat.db)
python chat_gui.py                         # terminal 2, 3, ... one per user
```
In the GUI: **Register** a new account, then **Login**. The defaults (`127.0.0.1`, port `5050`)
match the server. To chat across machines run the server with `--host 0.0.0.0` and enter that
machine's IP address in the client (see the security notes first).

On Debian/Ubuntu the GUI needs `sudo apt install python3-tk`.

## Protocol (Advanced tier)
One JSON object per line over TCP.

| Client → server | Purpose |
|---|---|
| `{"type":"register","username":..,"password":..}` | create an account |
| `{"type":"login","username":..,"password":..}` | sign in |
| `{"type":"join","room":..}` | create/join a room (leaves the current one) |
| `{"type":"message","text":..}` | send to the current room |
| `{"type":"rooms"}` / `{"type":"quit"}` | list rooms / disconnect |

Server replies: `registered`, `login_ok`, `joined` (members + history), `message`, `system`, `rooms`, `error`.

## Security transparency (what is stored, what is not encrypted)

**How data is stored** – in the server's SQLite file `chat.db`:
| Table | Contents |
|---|---|
| `users` | username, random 16-byte salt, PBKDF2 password hash, creation time. **Passwords are never stored in plain text.** |
| `rooms` | room name, creator, creation time |
| `messages` | room, sender, **message text in plain text**, timestamp |

**What is NOT encrypted or protected**
- **Network traffic is unencrypted plain TCP.** Anyone who can observe the network path can read
  messages **and the password sent at login/registration**. Use it only on `localhost` or a trusted
  network, and do not reuse a real password. (Production systems would wrap the sockets in TLS
  using `ssl.SSLContext` or use HTTPS/WSS.)
- **Messages are stored unencrypted** on the server, so the server operator and anyone with access to
  `chat.db` can read all history. There is **no end-to-end encryption**.
- Message history is kept indefinitely; there is no delete feature.
- There is no password-reset flow and no admin tooling.

**What is protected:** stored passwords (salted, slow hash, constant-time comparison), SQL injection
(parameterised queries), oversized/malformed input, and brute-force guessing (delay + disconnect).

## Testing
```bash
python -m unittest test_chat -v
```
35 end-to-end tests start real servers on random ports and exercise them over real sockets and
SQLite files: timestamps, disconnects, full/duplicate rules, packet reassembly, Unicode,
registration/login rules, hash storage, duplicate sessions, brute-force lock-out, rooms and
isolation, history limit and **persistence across a server restart**, SQL-injection text,
malformed JSON, oversized lines and emoji rendering.

The tkinter window itself is a thin layer over the tested `ChatConnection` class
(`chat_client_lib.py`) and needs a display, so it is checked manually.

## Project structure
```
task5_chat_application/
├── protocol.py          newline framing shared by all scripts
├── basic_server.py      Beginner: two-user server
├── basic_client.py      Beginner: command-line client
├── chat_server.py       Advanced: rooms, accounts, history (SQLite)
├── chat_client_lib.py   Advanced: network layer for clients
├── chat_gui.py          Advanced: tkinter client
├── emoji_codes.py       emoji shortcode rendering
├── test_chat.py         end-to-end tests
├── requirements.txt
└── README.md
```
