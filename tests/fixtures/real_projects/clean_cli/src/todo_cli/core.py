"""Core to-do list logic. Pure, deterministic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TodoList:
    """An ordered list of to-do items, each either open or done."""

    items: list[tuple[str, bool]] = field(default_factory=list)

    def add(self, text: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("item text must not be empty")
        self.items.append((text, False))

    def complete(self, index: int) -> None:
        text, _ = self.items[index]
        self.items[index] = (text, True)

    def pending(self) -> list[str]:
        return [text for text, done in self.items if not done]


def format_list(todo: TodoList) -> str:
    """Render the list as stable, line-oriented text."""
    lines = []
    for i, (text, done) in enumerate(todo.items):
        mark = "x" if done else " "
        lines.append(f"{i}. [{mark}] {text}")
    return "\n".join(lines)
