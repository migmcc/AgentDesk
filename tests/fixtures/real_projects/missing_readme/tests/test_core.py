"""Passing tests for the wordcount fixture (which deliberately lacks a README)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wordcount.core import count_words, top_word


def test_count_words():
    assert count_words("one two three") == 3


def test_top_word():
    assert top_word("a b a c a") == "a"


def test_top_word_empty():
    assert top_word("") is None
