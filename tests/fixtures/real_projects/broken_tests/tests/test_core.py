"""Tests for the calc fixture. `test_subtract` fails on purpose (intentional bug)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calc.core import add, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    # Fails because calc.core.subtract is intentionally buggy.
    assert subtract(5, 3) == 2
