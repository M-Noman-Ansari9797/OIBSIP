"""
Task 1 - Voice Assistant (Beginner + Advanced tiers)

Listens to spoken commands through the microphone and responds with speech.

Beginner features
    * Voice capture with speech_recognition
    * Greeting on "hello"
    * Current time and date
    * Web search by voice
    * Graceful "please repeat" handling
    * Text-to-speech replies with pyttsx3

Advanced features
    * Intent parsing from free-form sentences (scored intent matching, no
      single-keyword dependence)
    * Send e-mail by voice (smtplib, test account)
    * Timed reminders with an audible alert
    * Live weather (OpenWeatherMap free tier)
    * General-knowledge answers (Wikipedia summary API + local knowledge base)
    * User-defined custom commands from custom_commands.json or by voice

Run:  python assistant.py            (voice mode)
      python assistant.py --text     (type commands; useful without a microphone)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import smtplib
import threading
import webbrowser
from email.message import EmailMessage
from pathlib import Path

import requests

try:  # Audio libraries are optional so the logic can still be imported/tested.
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None

try:
    import pyttsx3
except ImportError:  # pragma: no cover
    pyttsx3 = None

BASE_DIR = Path(__file__).resolve().parent
CUSTOM_COMMANDS_FILE = BASE_DIR / "custom_commands.json"
LOCAL_KB_FILE = BASE_DIR / "knowledge_base.json"

# Secrets come from environment variables, never from source code.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # use an app password / test account
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Islamabad")

# Small contact book so e-mail can be addressed by name (edit as needed).
CONTACTS = {
    "test": os.getenv("SMTP_USER", "test@example.com"),
}


# --------------------------------------------------------------------------
# Speech input / output
# --------------------------------------------------------------------------
class Speaker:
    """Text-to-speech wrapper. Falls back to printing if pyttsx3 is missing."""

    def __init__(self) -> None:
        self.engine = None
        if pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", 170)
            except Exception as exc:  # no audio device / driver
                print(f"[warning] Text-to-speech unavailable: {exc}")

    def say(self, text: str) -> None:
        print(f"Assistant: {text}")
        if self.engine is None:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except RuntimeError:
            # runAndWait can raise if called while the loop is already running
            # (for example from a reminder thread). Printing is enough then.
            pass


class Listener:
    """Captures a spoken phrase from the microphone (or typed text)."""

    def __init__(self, text_mode: bool = False) -> None:
        self.text_mode = text_mode or sr is None
        if self.text_mode and not text_mode:
            print("[warning] speech_recognition not installed - using text mode.")
        if not self.text_mode:
            self.recognizer = sr.Recognizer()
            self.recognizer.pause_threshold = 0.8

    def listen(self, prompt: str = "Listening...") -> str | None:
        if self.text_mode:
            try:
                return input("You: ").strip().lower() or None
            except EOFError:
                return "exit"

        with sr.Microphone() as source:
            print(prompt)
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                return None
        try:
            text = self.recognizer.recognize_google(audio).lower()
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            return None  # speech was not understood
        except sr.RequestError as exc:
            print(f"[error] Speech service unavailable: {exc}")
            return None


# --------------------------------------------------------------------------
# Intent recognition (Advanced: free-form sentences, not one keyword)
# --------------------------------------------------------------------------
INTENT_PATTERNS: dict[str, list[str]] = {
    "greeting": ["hello", "hi", "hey", "good morning", "good evening", "good afternoon"],
    "time": ["time", "clock", "what hour", "current time"],
    "date": ["date", "today", "day is it", "what day", "month"],
    "search": ["search", "google", "look up", "look for", "find information", "browse"],
    "weather": ["weather", "temperature", "forecast", "how hot", "how cold", "raining", "rain"],
    "email": ["email", "e-mail", "mail", "send a message", "write to"],
    "reminder": ["remind", "reminder", "alarm", "timer", "alert me", "wake me"],
    "add_command": ["add command", "new command", "teach you", "add a command", "create command"],
    "knowledge": ["who is", "who was", "what is", "what are", "what was", "tell me about",
                  "explain", "define", "capital of", "how many", "when was", "where is"],
    "exit": ["exit", "quit", "goodbye", "bye", "stop listening", "shut down"],
}

# Phrases that are much stronger evidence than a single word.
STRONG_PHRASES = {
    "time": ["what time", "current time", "tell me the time"],
    "date": ["what date", "today's date", "what day"],
    "weather": ["weather in", "weather like", "how is the weather"],
    "reminder": ["remind me", "set a reminder", "set a timer", "set an alarm"],
    "email": ["send an email", "send email", "write an email"],
    "search": ["search for", "search the web", "look up", "google"],
    "knowledge": ["who is", "what is", "tell me about", "capital of"],
    "greeting": ["hello", "good morning", "good evening"],
}


def classify_intent(utterance: str) -> tuple[str, float]:
    """Score every intent against the sentence and return the best one.

    The score counts whole-word / phrase matches, weights multi-word phrases
    more heavily, and lightly favours earlier matches so that
    "search for the weather report" still resolves to *search*.
    """
    text = f" {utterance.lower().strip()} "
    scores: dict[str, float] = {}

    for intent, keywords in INTENT_PATTERNS.items():
        score = 0.0
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                score += 1.0 + 0.5 * kw.count(" ")
        for phrase in STRONG_PHRASES.get(intent, []):
            if phrase in text:
                score += 2.0
        if score:
            scores[intent] = score

    if not scores:
        return "unknown", 0.0

    # Tie-break: the intent whose earliest keyword appears first in the sentence.
    def first_position(intent: str) -> int:
        positions = [text.find(k) for k in INTENT_PATTERNS[intent] if k in text]
        return min(positions) if positions else len(text)

    best = max(scores, key=lambda i: (scores[i], -first_position(i)))
    total = sum(scores.values())
    return best, scores[best] / total


# --------------------------------------------------------------------------
# Entity extraction helpers
# --------------------------------------------------------------------------
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "forty five": 45, "sixty": 60,
}


def parse_duration(text: str) -> int | None:
    """Return a duration in seconds from phrases like 'in 5 minutes'."""
    match = re.search(
        r"(\d+(?:\.\d+)?|\b(?:" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\b)\s*"
        r"(seconds?|secs?|minutes?|mins?|hours?|hrs?)",
        text,
    )
    if not match:
        return None
    raw, unit = match.group(1), match.group(2)
    value = float(raw) if re.fullmatch(r"\d+(?:\.\d+)?", raw) else NUMBER_WORDS[raw]
    if unit.startswith(("hour", "hr")):
        return int(value * 3600)
    if unit.startswith(("min",)):
        return int(value * 60)
    return int(value)


def extract_search_query(text: str) -> str:
    cleaned = re.sub(
        r"^(please\s+)?(can you\s+)?(search( the web)?( for)?|google|look up|look for|find information (about|on))\s*",
        "", text.strip(), flags=re.I,
    )
    cleaned = re.sub(r"\s+(on|in) (google|the web|the internet)$", "", cleaned)
    return cleaned.strip()


def extract_city(text: str) -> str:
    match = re.search(r"(?:weather|temperature|forecast)\s+(?:in|at|for|of)\s+([a-z\s]+)", text)
    if match:
        city = re.sub(r"\b(today|tomorrow|now|please|right now)\b", "", match.group(1)).strip()
        if city:
            return city.title()
    return DEFAULT_CITY


def extract_topic(text: str) -> str:
    topic = re.sub(
        r"^(please\s+)?(can you\s+)?(tell me about|who is|who was|what is|what are|what was|"
        r"explain|define|when was|where is|how many)\s+(a |an |the )?",
        "", text.strip(), flags=re.I,
    )
    return topic.strip(" ?")


# --------------------------------------------------------------------------
# Custom commands (Advanced)
# --------------------------------------------------------------------------
def load_custom_commands() -> dict[str, dict]:
    if CUSTOM_COMMANDS_FILE.exists():
        try:
            return json.loads(CUSTOM_COMMANDS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print("[warning] custom_commands.json is unreadable; ignoring it.")
    return {}


def save_custom_commands(commands: dict[str, dict]) -> None:
    CUSTOM_COMMANDS_FILE.write_text(json.dumps(commands, indent=2), encoding="utf-8")


def load_local_kb() -> dict[str, str]:
    if LOCAL_KB_FILE.exists():
        try:
            return json.loads(LOCAL_KB_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


# --------------------------------------------------------------------------
# The assistant
# --------------------------------------------------------------------------
class VoiceAssistant:
    def __init__(self, text_mode: bool = False) -> None:
        self.speaker = Speaker()
        self.listener = Listener(text_mode=text_mode)
        self.custom_commands = load_custom_commands()
        self.local_kb = load_local_kb()
        self.running = True

    # -- helpers ----------------------------------------------------------
    def say(self, text: str) -> None:
        self.speaker.say(text)

    def ask(self, question: str, retries: int = 2) -> str | None:
        """Ask a follow-up question and return the answer (or None)."""
        for _ in range(retries + 1):
            self.say(question)
            answer = self.listener.listen()
            if answer:
                return answer
            self.say("Sorry, I did not catch that.")
        return None

    # -- skills -----------------------------------------------------------
    def do_greeting(self, _: str) -> None:
        hour = dt.datetime.now().hour
        part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        self.say(f"Hello! Good {part}. How can I help you?")

    def do_time(self, _: str) -> None:
        self.say(f"The time is {dt.datetime.now():%I:%M %p}.")

    def do_date(self, _: str) -> None:
        self.say(f"Today is {dt.datetime.now():%A, %d %B %Y}.")

    def do_search(self, text: str) -> None:
        query = extract_search_query(text)
        if not query:
            query = self.ask("What would you like me to search for?") or ""
        if not query:
            return
        self.say(f"Searching the web for {query}.")
        webbrowser.open("https://www.google.com/search?q=" + requests.utils.quote(query))

    def do_weather(self, text: str) -> None:
        if not OPENWEATHER_API_KEY:
            self.say("Weather needs an OpenWeatherMap API key. Please set OPENWEATHER_API_KEY.")
            return
        city = extract_city(text)
        try:
            resp = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"},
                timeout=8,
            )
            if resp.status_code == 404:
                self.say(f"I could not find a city called {city}.")
                return
            resp.raise_for_status()
            data = resp.json()
            desc = data["weather"][0]["description"]
            temp = round(data["main"]["temp"])
            feels = round(data["main"]["feels_like"])
            humidity = data["main"]["humidity"]
            self.say(
                f"In {city} it is {temp} degrees Celsius with {desc}. "
                f"It feels like {feels}, and humidity is {humidity} percent."
            )
        except requests.RequestException:
            self.say("I could not reach the weather service. Please check your connection.")

    def do_email(self, _: str) -> None:
        if not (SMTP_USER and SMTP_PASSWORD):
            self.say("E-mail is not configured. Set SMTP_USER and SMTP_PASSWORD for a test account.")
            return
        who = self.ask("Who should I send it to? Say a contact name.")
        if not who:
            return
        recipient = CONTACTS.get(who.strip().lower())
        if not recipient:
            self.say(f"I do not have a contact called {who}.")
            return
        subject = self.ask("What is the subject?") or "Message from voice assistant"
        body = self.ask("What should the message say?")
        if not body:
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = SMTP_USER, recipient, subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            self.say("Your email has been sent.")
        except (smtplib.SMTPException, OSError) as exc:
            print(f"[error] {exc}")
            self.say("Sorry, I could not send the email.")

    def do_reminder(self, text: str) -> None:
        seconds = parse_duration(text)
        if seconds is None:
            answer = self.ask("After how long should I remind you?")
            seconds = parse_duration(answer or "")
        if not seconds:
            self.say("I could not understand the duration.")
            return
        label = re.sub(r".*\b(?:to|about|that)\b\s+", "", text) if re.search(r"\b(to|about|that)\b", text) else ""
        label = re.sub(r"\b(in|after)\b.*$", "", label).strip()
        self.say(f"Okay, I will remind you in {format_duration(seconds)}.")
        timer = threading.Timer(seconds, self._fire_reminder, args=(label,))
        timer.daemon = True
        timer.start()

    def _fire_reminder(self, label: str) -> None:
        message = f"Reminder: {label}" if label else "Your timer is up."
        print(f"\n*** {message} ***")
        try:  # audible alert independent of TTS
            import winsound  # type: ignore
            for _ in range(3):
                winsound.Beep(1000, 400)
        except ImportError:
            print("\a", end="", flush=True)
        self.say(message)

    def do_knowledge(self, text: str) -> None:
        topic = extract_topic(text)
        if not topic:
            self.say("What would you like to know about?")
            return
        key = topic.lower()
        if key in self.local_kb:  # local knowledge base first
            self.say(self.local_kb[key])
            return
        try:
            resp = requests.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/"
                + requests.utils.quote(topic.replace(" ", "_")),
                timeout=8, headers={"User-Agent": "InternshipVoiceAssistant/1.0"},
            )
            if resp.status_code == 200:
                extract = resp.json().get("extract", "")
                sentences = re.split(r"(?<=[.!?])\s+", extract)
                self.say(" ".join(sentences[:2]) or "I found no summary for that.")
            else:
                self.say(f"I could not find information about {topic}. Let me search the web instead.")
                webbrowser.open("https://www.google.com/search?q=" + requests.utils.quote(topic))
        except requests.RequestException:
            self.say("I could not reach the knowledge service.")

    def do_add_command(self, _: str) -> None:
        trigger = self.ask("What phrase should trigger the new command?")
        if not trigger:
            return
        kind = self.ask("Should it open a website, or say a reply? Say website or reply.")
        if not kind:
            return
        if "web" in kind:
            target = self.ask("Say the web address, for example example dot com.")
            if not target:
                return
            target = target.replace(" dot ", ".").replace(" ", "")
            if not target.startswith("http"):
                target = "https://" + target
            self.custom_commands[trigger] = {"action": "open_url", "value": target}
        else:
            reply = self.ask("What should I say?")
            if not reply:
                return
            self.custom_commands[trigger] = {"action": "say", "value": reply}
        save_custom_commands(self.custom_commands)
        self.say(f"Done. Say {trigger} to use your new command.")

    def do_exit(self, _: str) -> None:
        self.say("Goodbye!")
        self.running = False

    # -- dispatch ---------------------------------------------------------
    def try_custom_command(self, text: str) -> bool:
        for trigger, spec in self.custom_commands.items():
            if trigger.lower() in text:
                if spec.get("action") == "open_url":
                    self.say(f"Opening {spec['value']}")
                    webbrowser.open(spec["value"])
                else:
                    self.say(spec.get("value", ""))
                return True
        return False

    def handle(self, text: str) -> None:
        if self.try_custom_command(text):
            return
        intent, confidence = classify_intent(text)
        handler = getattr(self, f"do_{intent}", None)
        if handler is None or confidence < 0.3:
            self.say("I am not sure what you mean. You can ask me for the time, weather, "
                     "a web search, a reminder, or to send an email.")
            return
        handler(text)

    def run(self) -> None:
        self.say("Voice assistant ready. Say hello to begin, or say exit to quit.")
        while self.running:
            text = self.listener.listen()
            if text is None:
                self.say("Sorry, I did not understand. Could you please repeat that?")
                continue
            self.handle(text)


def format_duration(seconds: int) -> str:
    parts = []
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    return " and ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Python voice assistant")
    parser.add_argument("--text", action="store_true", help="type commands instead of speaking")
    args = parser.parse_args()
    try:
        VoiceAssistant(text_mode=args.text).run()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
