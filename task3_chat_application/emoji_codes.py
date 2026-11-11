"""Emoji shortcode rendering, e.g. ':smile:' -> a smiling-face emoji."""

from __future__ import annotations

import re

EMOJI = {
    "smile": "\U0001F604", "grin": "\U0001F601", "joy": "\U0001F602", "laughing": "\U0001F606",
    "wink": "\U0001F609", "blush": "\U0001F60A", "heart_eyes": "\U0001F60D", "sunglasses": "\U0001F60E",
    "thinking": "\U0001F914", "neutral_face": "\U0001F610", "cry": "\U0001F622", "sob": "\U0001F62D",
    "angry": "\U0001F620", "scream": "\U0001F631", "sleepy": "\U0001F62A", "confused": "\U0001F615",
    "thumbsup": "\U0001F44D", "+1": "\U0001F44D", "thumbsdown": "\U0001F44E", "-1": "\U0001F44E",
    "clap": "\U0001F44F", "wave": "\U0001F44B", "pray": "\U0001F64F", "muscle": "\U0001F4AA",
    "ok_hand": "\U0001F44C", "raised_hands": "\U0001F64C",
    "heart": "❤️", "broken_heart": "\U0001F494", "star": "⭐", "fire": "\U0001F525",
    "sparkles": "✨", "tada": "\U0001F389", "100": "\U0001F4AF", "rocket": "\U0001F680",
    "check": "✅", "x": "❌", "warning": "⚠️", "bulb": "\U0001F4A1",
    "coffee": "☕", "pizza": "\U0001F355", "cake": "\U0001F382", "gift": "\U0001F381",
    "sun": "☀️", "moon": "\U0001F319", "snake": "\U0001F40D", "computer": "\U0001F4BB",
}

_PATTERN = re.compile(r":([a-z0-9_+\-]+):", re.IGNORECASE)


def render_emoji(text: str) -> str:
    """Replace known :shortcodes: with Unicode emoji; unknown codes are left untouched."""
    return _PATTERN.sub(lambda m: EMOJI.get(m.group(1).lower(), m.group(0)), text)
