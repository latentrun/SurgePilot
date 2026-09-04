from __future__ import annotations

import secrets
import time

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    timestamp_ms = int(time.time() * 1000)
    random_bits = secrets.randbits(80)
    value = (timestamp_ms << 80) | random_bits
    chars: list[str] = []
    for index in range(26):
        shift = (25 - index) * 5
        chars.append(CROCKFORD_ALPHABET[(value >> shift) & 0b11111])
    return "".join(chars)


def new_request_id() -> str:
    return f"req_{new_ulid()}"


def is_ulid(value: str) -> bool:
    return len(value) == 26 and all(character in CROCKFORD_ALPHABET for character in value)
