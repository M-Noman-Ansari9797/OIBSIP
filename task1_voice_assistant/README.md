# Task 1 – Voice Assistant (Python)

A voice-controlled assistant that listens through the microphone, understands free-form
sentences and answers aloud. Implemented at the **Advanced tier** (which includes every
Beginner feature).

## Features

### Beginner tier
| Requirement | Where |
|---|---|
| Voice input via `speech_recognition` | `Listener.listen()` |
| Responds to "Hello" | `VoiceAssistant.do_greeting()` |
| Tells current time and date | `do_time()`, `do_date()` |
| Web search by voice (opens browser) | `do_search()` |
| Asks user to repeat when speech is not understood | `VoiceAssistant.run()` |
| Spoken replies with `pyttsx3` | `Speaker.say()` |

### Advanced tier
| Requirement | Where |
|---|---|
| Intent parsing from free-form sentences | `classify_intent()` – weighted phrase/word scoring with confidence threshold |
| Send e-mail by voice (`smtplib`) | `do_email()` – asks for contact, subject, body step by step |
| Timed reminder with audible alert | `do_reminder()` + `parse_duration()` (threaded timer, beep + spoken alert) |
| Live weather (OpenWeatherMap) | `do_weather()` |
| General-knowledge questions | `do_knowledge()` – local `knowledge_base.json`, then Wikipedia summary API |
| Custom commands via config file or voice | `custom_commands.json`, `do_add_command()` |
| Privacy documentation | see **Privacy** below |

## Setup

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

`PyAudio` setup by platform:
* **Windows:** `pip install pyaudio` (or `pipwin install pyaudio` if the wheel fails)
* **macOS:** `brew install portaudio` then `pip install pyaudio`
* **Linux:** `sudo apt install portaudio19-dev python3-pyaudio espeak`

### Environment variables (never hard-code secrets)
| Variable | Purpose |
|---|---|
| `OPENWEATHER_API_KEY` | Free key from openweathermap.org |
| `SMTP_USER`, `SMTP_PASSWORD` | A **test/dummy** mail account (use an app password) |
| `SMTP_HOST`, `SMTP_PORT` | Optional (default Gmail `smtp.gmail.com:587`) |
| `DEFAULT_CITY` | Optional (default `Islamabad`) |

Windows example: `setx OPENWEATHER_API_KEY "your_key_here"` (restart the terminal).

## Run

```bash
python assistant.py          # voice mode
python assistant.py --text   # type commands (no microphone needed)
```

## Example commands

* "Hello"
* "What time is it?" / "What's today's date?"
* "Could you look up Python tutorials for me"
* "How is the weather in Lahore?"
* "Remind me to drink water in 10 minutes"
* "I want to send an email" (assistant then asks for contact, subject and message)
* "Who is Albert Einstein?"
* "Add command" (teach a new phrase by voice) or edit `custom_commands.json`
* "Goodbye"

## Testing

```bash
python -m unittest test_assistant -v
```
The 10 unit tests cover intent classification, duration parsing, and entity extraction.

## Privacy

| Data | Processing | Stored? |
|---|---|---|
| Microphone audio | Captured only while listening; sent to Google's free Web Speech API through `recognize_google()` for transcription | Not saved by this program |
| Transcribed text | Handled locally to choose an action | Kept in memory only; not logged |
| Weather city | Sent to OpenWeatherMap | Not stored locally |
| Knowledge questions | Topic sent to Wikipedia's public API when not in the local KB | Not stored locally |
| E-mail content | Sent through the SMTP server you configure | Not stored locally |
| Custom commands | Saved in `custom_commands.json` on your machine | Yes (only what you add) |
| API keys / passwords | Read from environment variables | Never written to disk by the program |

Because transcription uses an online service, audio leaves the device. For an offline
option swap `recognize_google` for `recognize_sphinx` (PocketSphinx). Use a dummy e-mail
account while testing.

## Project structure
```
task1_voice_assistant/
├── assistant.py            main program
├── test_assistant.py       unit tests
├── custom_commands.json    user-defined commands
├── knowledge_base.json     local Q&A knowledge base
├── requirements.txt
└── README.md
```
