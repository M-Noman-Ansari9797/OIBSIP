"""Task 3 - Random Password Generator (Beginner tier: command line, random + string).

The Beginner tier intentionally uses the `random` and `string` modules as specified.
For real-world security use the Advanced version (password_gui.py / password_core.py),
which relies on the `secrets` module instead.
"""

import random
import string

MIN_LENGTH = 8

TYPES = {
    "1": ("uppercase letters", string.ascii_uppercase),
    "2": ("lowercase letters", string.ascii_lowercase),
    "3": ("numbers", string.digits),
    "4": ("symbols", "!@#$%^&*()-_=+[]{};:,.<>?"),
}


def ask_length() -> int:
    while True:
        raw = input(f"Password length (minimum {MIN_LENGTH}): ").strip()
        if not raw.isdigit():
            print("  Please enter a whole number, e.g. 12.")
            continue
        length = int(raw)
        if length < MIN_LENGTH:
            print(f"  Length must be at least {MIN_LENGTH} characters.")
            continue
        if length > 128:
            print("  Length must not exceed 128 characters.")
            continue
        return length


def ask_types() -> list[str]:
    print("\nChoose character types (at least 2), e.g. 1,2,3 :")
    for key, (name, _) in TYPES.items():
        print(f"  {key}) {name}")
    while True:
        raw = input("Your choice: ").replace(" ", "")
        picks = {p for p in raw.split(",") if p}
        if not picks or not picks <= set(TYPES):
            print("  Enter numbers from 1 to 4 separated by commas.")
            continue
        if len(picks) < 2:
            print("  Please select at least 2 character types.")
            continue
        return sorted(picks)


def generate(length: int, picks: list[str]) -> str:
    pools = [TYPES[p][1] for p in picks]
    chars = [random.choice(pool) for pool in pools]          # one from each type
    all_chars = "".join(pools)
    chars += [random.choice(all_chars) for _ in range(length - len(chars))]
    random.shuffle(chars)
    return "".join(chars)


def main() -> None:
    print("=== Random Password Generator ===\n")
    while True:
        length = ask_length()
        picks = ask_types()
        print(f"\nGenerated password: {generate(length, picks)}\n")
        again = input("Generate another password? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("Goodbye - keep your passwords private!")
            break
        print()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nProgram closed.")
