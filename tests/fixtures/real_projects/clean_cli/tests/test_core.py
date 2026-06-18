"""Passing tests for the todo-cli fixture."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from todo_cli.core import TodoList, format_list


def test_add_and_pending():
    todo = TodoList()
    todo.add("write tests")
    todo.add("ship it")
    assert todo.pending() == ["write tests", "ship it"]


def test_complete_removes_from_pending():
    todo = TodoList()
    todo.add("write tests")
    todo.complete(0)
    assert todo.pending() == []


def test_format_is_stable():
    todo = TodoList()
    todo.add("a")
    todo.complete(0)
    assert format_list(todo) == "0. [x] a"
