# Python Programming Internship – Task Submission

**Track:** Python Programming  **Organisation:** Oasis Infobyte (SIP)
**Tasks completed:** 5 of 5, each at the **Advanced tier** (which includes every Beginner feature).
The completion rule requires at least 3 of 5.

| # | Task | Beginner tier | Advanced tier | Tests |
|---|------|---------------|---------------|-------|
| 1 | Voice Assistant | Voice input, greeting, time/date, web search, repeat-on-error, spoken replies | Intent parsing, voice e-mail (smtplib), timed reminders, live weather, Q&A, custom commands, privacy notes | 10 |
| 2 | BMI Calculator | Command-line BMI with validation | tkinter GUI, colour-coded result, multi-user, SQLite history, matplotlib trend chart | 12 |
| 3 | Random Password Generator | Command-line (`random`/`string`) | tkinter GUI, `secrets`, strength meter, clipboard, ambiguous-character option, 5-item history | 13 |
| 4 | Basic Weather App | Command-line, °C/°F, error handling | tkinter GUI, icons, 6-hour and 5-day forecasts, unit toggle, IP location bonus | 18 |
| 5 | Chat Application | Two-user socket chat with timestamps | Accounts (hashed passwords), rooms, history, emoji, notifications, security documentation | 35 |

Each folder contains its source code, a `README.md` (features, setup, usage, design notes),
`requirements.txt`, and a unit-test file.

## Quick start
```bash
cd task2_bmi_calculator
pip install -r requirements.txt
python bmi_cli.py            # Beginner tier
python bmi_gui.py            # Advanced tier
python -m unittest -v        # run the tests
```
Requires Python 3.10 or newer. tkinter ships with the standard Windows/macOS installers
(`sudo apt install python3-tk` on Debian/Ubuntu).

## API keys and secrets
Tasks 1 and 4 need a free OpenWeatherMap key and Task 1's e-mail feature needs a test mailbox.
These are read from environment variables (`OPENWEATHER_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`)
and are never stored in the code. See each task's README.

## Verification summary
* 88 automated tests, all passing; every script compiles cleanly.
* Network-dependent code (weather API, IP lookup) is tested with mocked responses.
* The chat server is tested end to end over real sockets and real SQLite databases.
* The tkinter windows, microphone / text-to-speech, live API calls and SMTP sending need a desktop,
  hardware or credentials and were verified at code and logic level rather than launched.
