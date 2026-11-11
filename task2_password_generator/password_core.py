"""Shared password logic for the CLI (random/string) and GUI (secrets) versions."""

from __future__ import annotations

import secrets
import string

AMBIGUOUS = set("0Oo1lI|")

CHARSETS = {
    "uppercase": string.ascii_uppercase,
    "lowercase": string.ascii_lowercase,
    "numbers": string.digits,
    "symbols": "!@#$%^&*()-_=+[]{};:,.<>?/~",
}

MIN_LENGTH = 8
MAX_LENGTH = 128


def build_pools(selected: list[str], exclude_ambiguous: bool = False) -> dict[str, str]:
    """Return {type: characters} for each selected type, optionally dropping look-alikes."""
    pools: dict[str, str] = {}
    for name in selected:
        if name not in CHARSETS:
            raise ValueError(f"Unknown character type: {name}")
        chars = CHARSETS[name]
        if exclude_ambiguous:
            chars = "".join(c for c in chars if c not in AMBIGUOUS)
        pools[name] = chars
    return pools


def validate_request(length: int, selected: list[str]) -> None:
    if not MIN_LENGTH <= length <= MAX_LENGTH:
        raise ValueError(f"Length must be between {MIN_LENGTH} and {MAX_LENGTH}.")
    if len(selected) < 2:
        raise ValueError("Select at least 2 character types.")
    if length < len(selected):
        raise ValueError("Length is too short for the selected character types.")


def generate_password(length: int, selected: list[str], exclude_ambiguous: bool = False) -> str:
    """Cryptographically secure password with >=1 character from every selected type."""
    validate_request(length, selected)
    pools = build_pools(selected, exclude_ambiguous)

    # Guarantee one character from every chosen type...
    chars = [secrets.choice(pool) for pool in pools.values()]
    # ...fill the remainder from the combined pool...
    combined = "".join(pools.values())
    chars += [secrets.choice(combined) for _ in range(length - len(chars))]
    # ...and shuffle with a CSPRNG so the guaranteed characters are not predictable.
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def strength(password: str) -> tuple[str, int]:
    """Return (label, score 0-100) based on length and character diversity."""
    kinds = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    length = len(password)
    score = min(length, 24) * 2.5 + kinds * 10          # up to 60 + 40
    if len(set(password)) < length * 0.5:               # many repeats weaken it
        score -= 15
    score = max(0, min(100, int(score)))

    if length < 10 or kinds < 2 or score < 50:
        return "Weak", score
    if length < 14 or kinds < 3 or score < 80:
        return "Medium", score
    return "Strong", score
