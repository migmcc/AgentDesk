"""Pure word-counting logic, no I/O."""

from __future__ import annotations

from collections import Counter


def count_words(text: str) -> int:
    return len(text.split())


def top_word(text: str) -> str | None:
    """Most common word, or None for empty text. Ties resolved by first appearance."""
    words = text.split()
    if not words:
        return None
    return Counter(words).most_common(1)[0][0]
