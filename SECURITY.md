# Security Policy

Agent Desk is a **local-first** developer tool. It runs entirely on your machine, makes no network
calls of its own, and stores no credentials. The only outbound traffic it can make is to a
**local model endpoint you configure yourself** (e.g. Ollama), and the only thing it executes is a
test command you pass explicitly to `agentdesk validate-project --test-command`.

## Supported versions

Security fixes are provided for the latest released minor series only.

| Version | Supported |
| ------- | --------- |
| 0.4.x   | ✅ Yes    |
| < 0.4.0 | ❌ No     |

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a suspected
vulnerability.

- Preferred: use GitHub's private vulnerability reporting on this repository
  (**Security** tab → **Report a vulnerability**).
- Alternatively, contact the maintainer (see the commit history / repository owner) directly.

When reporting, please include:

- a description of the issue and its impact,
- steps to reproduce (a minimal example is ideal),
- the Agent Desk version (`agentdesk version`) and your OS / Python version.

We aim to acknowledge a valid report within a reasonable time for a single-maintainer project and
will coordinate a fix and disclosure timeline with you.

## Scope and guarantees

- **No guarantees are made for unreleased work** — feature branches, pre-release commits, and
  anything not part of a tagged release.
- The project ships with no secrets and adds no external runtime dependencies; if you discover a
  committed secret or an unexpected network call, that itself is a reportable issue.
- Hardening of any local model endpoint you configure (authentication, network exposure) is your
  responsibility, as that endpoint is outside Agent Desk.
