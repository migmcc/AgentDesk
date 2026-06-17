# Agent Desk — Decisions

Locked decisions for Agent Desk (approved 2026-06-17).

## D1 — Routing: fixed rules + manual override (no scoring in MVP)
Simpler, predictable, debuggable. The system recommends a model; the user can override manually.
Routing always records: recommended model, reason, alternative model, and whether an override
occurred. Initial table by task type:

| Task type      | Recommended | Alternative |
|----------------|-------------|-------------|
| planning       | claude-code | local |
| architecture   | claude-code | codex |
| setup          | codex       | claude-code |
| implementation | codex       | claude-code |
| bugfix         | codex       | claude-code |
| testing        | codex       | claude-code |
| refactor       | claude-code | codex |
| documentation  | local       | claude-code |
| review         | local (low risk) / claude-code (structural) | — |
| handover       | local       | claude-code |
| quality-gate   | internal system; + claude-code if risk medium/high | — |
| research       | local (low) / claude-code (high criticality) | — |

## D2 — Risk levels: low / medium / high
- **Low** — docs only; isolated new files; tests without touching core logic; summaries; handovers;
  no architecture/contract change; no data/auth/payments/critical-config. Local model allowed.
- **Medium** — app logic; 1–3 modules; simple data-model changes; small feature; limited-impact bug
  fix; tests+impl together. Codex (impl) / Claude Code (analysis); local for support only.
  **Quality gate mandatory.**
- **High** — architecture; large refactor; many modules; public/API contracts; auth/security/
  permissions/persistent data; migrations; code removal; global config; vague criteria; shared
  files. Claude Code (plan); Codex only if tightly bounded; **local forbidden for execution.**
  **Quality gate mandatory + human review recommended.**

`router.local_model_allowed(task_type, risk)`: high → never; low → always; medium → only for
support-style types (documentation, handover, review, research).

## D3 — Git: not actively integrated in MVP (deferred to Phase 4)
MVP uses SQLite state + per-file locking only. The Task schema is **Git-ready** with optional fields
that need not function yet: `branch_name`, `base_branch`, `commit_hash`, `changed_files`, `pr_url`,
`diff_summary`.

## D4 — Standalone repository
Standalone repository, developed independently from other incubation and planning work.

## D5 — License: MIT
MIT is the project's definitive license (confirmed at the v0.1.0 release). See `LICENSE`.
