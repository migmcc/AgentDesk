"""Prompt generator — produce model-specific prompts (Codex / Claude Code / local).

Run C. Loads a task, picks the template for the chosen model, renders it (with a dependency
warning when the task is blocked), and writes it to prompts/<model-dir>/TASK-XXX.md.
"""

from agentdesk.prompt_generator.generator import (
    MODEL_DIRS,
    MODEL_TEMPLATES,
    generate_prompt,
    prompt_relpath,
    render_prompt,
)

__all__ = [
    "generate_prompt",
    "render_prompt",
    "prompt_relpath",
    "MODEL_DIRS",
    "MODEL_TEMPLATES",
]
