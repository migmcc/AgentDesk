"""Quality gate — evaluate whether a task's work can be accepted.

Run E. Deterministic: produces a GateResult (PASS / PASS_WITH_WARNINGS / FAIL /
NEEDS_HUMAN_REVIEW) from observable task/handover/lock/dependency data. No Git, diffs, or LLM.
"""

from agentdesk.quality_gate.gate import run_gate

__all__ = ["run_gate"]
