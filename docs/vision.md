# Agent Desk — Vision

## Problem
Solo builders working with multiple AI models (Codex, Claude Code, local models) lose time, tokens,
and quality: no clear vision at the start, vague prompts, expensive models on trivial tasks, lost
context between sessions, multiple models editing the same code, branch/file conflicts, no handover,
and no quality gate before accepting AI output.

## Target Audience
A solo builder running Codex + Claude Code + a local model (Ollama / LM Studio / OpenAI-compatible),
building several small/medium projects locally, cost-conscious, single-user.

## Proposed Solution
A local-first coordination layer **above** the models — not a replacement. It turns an idea into a
structured plan, decomposes it into small tasks, routes each task to the best model with a stated
reason, generates model-specific prompts, prevents conflicts via file locking, and validates work
with a quality gate before acceptance.

## Product Value
Multi-agent work that is more controlled, cheaper, and more consistent across sessions.

## MVP
CLI + Markdown + SQLite. Idea → docs → ≥10 routed tasks → per-model prompts → file locking →
state machine → handover → basic quality gate. Manual model execution (copy-paste prompts).

## Project Limits
No SaaS, no desktop UI, no multi-user, no automated model execution, no active Git integration,
no routing scoring — all deferred or out of scope (see docs/roadmap.md and docs/decisions.md).

## Success Criteria
- Turn a vague idea into a clear vision.
- Generate small, executable tasks.
- Recommend the right model per task, with a reason.
- Prevent simple file conflicts.
- Generate useful prompts; reduce rework; save paid tokens on simple tasks.
- Keep context across sessions — resume a project days later without losing direction.

## Recommended Decision
Advance — build the foundation (Run A), then iterate run by run.
