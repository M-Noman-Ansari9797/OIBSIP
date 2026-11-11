# Task 3 – Random Password Generator (Python)

Generates strong random passwords from user-defined criteria. Both tiers are included:
a **command-line** tool (Beginner, `random` + `string`) and a **tkinter GUI** (Advanced,
cryptographically secure `secrets`, strength meter, clipboard integration).

## Features

### Beginner tier – `password_cli.py`
- Asks for password length (minimum **8** enforced, maximum 128)
- Asks which character types to include: uppercase, lowercase, numbers, symbols (**at least 2** required)
- Generates and displays a password that satisfies every selected type
- Input validation: rejects non-numeric / too-short / too-long lengths, empty or invalid
  choices, and fewer than two types
- "Generate another?" loop – no restart needed

### Advanced tier – `password_gui.py`
- GUI with a **slider and spinbox** (kept in sync) for length and **checkboxes** for character types
- Uses the **`secrets`** module (not `random`) via `password_core.py`
- **Strength indicator** – coloured bar and Weak / Medium / Strong label, based on length,
  character diversity and repetition
- **Security rule enforced:** the password always contains at least one character from every
  selected type (verified by a 500-iteration test)
- **Copy to Clipboard** with `pyperclip` – the password is also copied automatically on each
  generation; double-click an item in the history to copy it again
- **Exclude ambiguous characters** checkbox (`0 O o 1 l I |`)
- **History of the last 5** passwords, kept in memory only – **never written to disk**

## Setup & run

```bash
pip install -r requirements.txt     # only needed for the GUI clipboard feature

python password_cli.py              # Beginner version
python password_gui.py              # Advanced version
```
On Debian/Ubuntu the GUI needs `sudo apt install python3-tk`; the clipboard on Linux also needs
`xclip` or `xsel`.

## How generation works
1. Validate length and selected types.
2. Pick one random character from each selected type (guarantees the security rule).
3. Fill the remaining length from the combined pool.
4. Shuffle with `secrets.SystemRandom()` so the guaranteed characters are not in predictable positions.

## Why `secrets` instead of `random`?
`random` is a predictable pseudo-random generator meant for simulations. `secrets` draws from the
operating system's cryptographically secure source, which is what security-sensitive values
such as passwords require. The Beginner version uses `random` only because the task specifies it.

## Testing
```bash
python -m unittest test_password -v
```
13 tests check exact length, presence of every selected type, no unselected types leaking in,
exclusion of ambiguous characters, uniqueness, all validation rules, and strength scoring.

## Security notes
- Passwords are not logged, saved or transmitted.
- History lives only in memory for the current session and is lost when the window closes.
- Clipboard contents may be readable by other applications until overwritten – clear it after use.

## Project structure
```
task3_password_generator/
├── password_core.py     secure generation + strength scoring
├── password_cli.py      Beginner tier (command line)
├── password_gui.py      Advanced tier (tkinter GUI)
├── test_password.py     unit tests
├── requirements.txt
└── README.md
```
