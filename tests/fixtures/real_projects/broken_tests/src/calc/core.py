"""Arithmetic core. NOTE: `subtract` is intentionally wrong for validation purposes."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    # BUG (intentional): should be `a - b`. Drives the "broken tests" scenario.
    return a + b
