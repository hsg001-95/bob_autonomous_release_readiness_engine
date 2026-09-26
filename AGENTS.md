# AGENTS.md — Galaxium Travels Verification Policies

## System Architecture Overview
Galaxium Travels is an enterprise booking platform composed of FastAPI, SQLite, and Node.js. Endpoints live under `src/api/v1/`, data models and migrations under `src/db/`, and dependencies are declared in `requirements.txt`.

## When Assessing Release Branches

- Treat all specification documents located in `docs/architecture/` as **immutable baselines** — the code must conform to them, not the reverse. If a spec appears wrong, escalate rather than reinterpret it.
- Maintain **zero tolerance** for unhandled exceptions, raw/string-concatenated SQL queries, or unvalidated API routes.
- **Optimize context hygiene**: always delegate deep directory exploration and dependency scans to isolated subagents (`spawn_subagent`); do not perform large-scale file sweeps in the primary session.
- Never proceed from Plan Mode to Agent Mode without explicit human confirmation of the verification plan.
- Critic subagents must always be spawned with `fork_context: false` when validating Actor-generated patches.

## Quality and Verification Standards

- **API Backward Compatibility**: modifying or removing existing attributes in `src/api/v1` routes requires deprecation aliasing.
- **Dependency Hygiene**: transitive dependencies with CVSS vulnerability scores exceeding 7.0 must be remediated.
- **Validation**: the entire test suite (`pytest tests/`) must execute cleanly before a release candidate is approved.

## Reference

Detailed code-generation and validation rules live in `.bob/rules/security.md`. The reusable audit procedure lives in `.bob/skills/release-readiness-audit/SKILL.md`.
