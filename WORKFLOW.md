# Workflow Documentation
## Autonomous Release Readiness and Governance Engine (RRE)

This document describes the end-to-end operational workflow, phase by phase, with the trigger, actor, inputs, outputs, and gate for each step.

---

## Phase 0 — Session Initialization

| | |
|---|---|
| **Trigger** | New Bob 2.0 session opened in the target repository |
| **Actor** | Coordinator |
| **Input** | `AGENTS.md`, `.bobignore` |
| **Action** | `AGENTS.md` is injected into the session context, establishing project standards and the zero-tolerance rules. `.bobignore` is applied to scope all subsequent read/write access. |
| **Output** | Governed session ready for invocation |
| **Gate** | None — automatic on session start |

## Phase 1 — Invocation

| | |
|---|---|
| **Trigger** | Interactive: `/release-readiness-audit Ingest @docs/architecture/rfc-042-booking-v2.pdf and evaluate ...` <br> Headless: `bob run --skill release-readiness-audit --mode Agent --context "..." --auto-approve "read,test" "..."` |
| **Actor** | User or CI runner |
| **Input** | Natural-language or CLI invocation referencing a spec document and target branch |
| **Action** | Bob loads `.bob/skills/release-readiness-audit/SKILL.md` and begins execution in **Plan Mode** |
| **Output** | Active audit session |
| **Gate** | None |

## Phase 2 — Specification Ingestion & Policy Extraction

| | |
|---|---|
| **Actor** | Coordinator (Plan Mode) |
| **Input** | Spec document (PDF/DOCX/MD) |
| **Action** | Docling parses tables, endpoint schemas, indexing rules, and auth policy out of the unstructured document into structured constraints |
| **Output** | Structured constraint set (endpoint contracts, DB rules, compliance clauses) |
| **Gate** | None — feeds directly into planning |

## Phase 3 — Verification Plan Construction

| | |
|---|---|
| **Actor** | Coordinator (Plan Mode) |
| **Input** | Structured constraints + repository file structure |
| **Action** | Evaluates constraints against repo layout; writes `plans/release-readiness-plan.md` detailing four verification streams (DB schema, dependency security, API contracts, regression testing) and a checklist via `update_todo_list` |
| **Output** | `plans/release-readiness-plan.md` |
| **Gate** | **Human approval required.** Execution does not proceed without explicit user confirmation of the plan. |

## Phase 4 — Parallel Subagent Audit

| | |
|---|---|
| **Actor** | Coordinator, transitioning to **Agent Mode**; spawns 3 subagents via `spawn_subagent` |
| **Input** | Approved plan + structured constraints |
| **Action** | Three subagents execute concurrently, each in an isolated context: <br>• `arch-auditor` (explore) — parses `src/db/models/*` and migration scripts; compares against spec-mandated indexing/constraints. <br>• `supply-sentinel` (explore) — parses `requirements.txt`/manifests; flags unpinned/outdated packages and dependencies above the CVSS threshold. <br>• `contract-guard` (general) — parses `src/api/**/routes/*`; compares request/response schemas against ingested contracts. <br>Each subagent returns a structured finding summary only; the UI aggregates them into a live subagent monitoring panel (tasks completed, tools invoked, tokens used, elapsed time). |
| **Output** | Consolidated findings list (schema drift, vulnerable dependencies, contract violations), each tagged with severity |
| **Gate** | None — automatic aggregation once all subagents complete |

## Phase 5 — Actor-Critic Remediation Loop

Runs once per High/Critical finding.

| | |
|---|---|
| **Actor step** | Coordinator, in Agent Mode, invokes the **Actor** skill: generates the minimal diff to resolve the finding (e.g., add a Pydantic schema, uplift a dependency version, add a missing composite index), constrained by `.bob/rules/security.md`. Patch is applied via `apply_diff`. |
| **Critic step** | Coordinator spawns an independent **Critic** subagent with `fork_context: false`. The Critic receives *only* the modified files and `.bob/rules/security.md` — no access to the Actor's prompt history or reasoning. It re-evaluates the patch against the rule book and OWASP ASVS Level 1, then runs the relevant test subset (e.g., `pytest tests/test_bookings.py -v`, `flake8 ...`). |
| **Output** | Accepted patch + test result, or rejected patch + Critic findings (loops back to Actor step) |
| **Gate** | Critic pass/fail is the gate; on repeated failure past a bounded retry count, the finding is escalated to the human reviewer rather than looped indefinitely |

## Phase 6 — Full Regression Validation

| | |
|---|---|
| **Actor** | Critic (final pass) or Coordinator |
| **Input** | All accepted patches |
| **Action** | Executes the full test suite (`pytest tests/`) to confirm no cross-cutting regressions beyond the targeted tests already run per-patch |
| **Output** | Pass/fail regression result |
| **Gate** | Full suite must pass before artifact generation proceeds to a "ready" state |

## Phase 7 — Artifact Generation

| | |
|---|---|
| **Actor** | Coordinator |
| **Input** | All findings, accepted patches, test results |
| **Action** | Compiles `security/audit-results.sarif` (SARIF 2.1.0 — each finding mapped to rule ID, severity, location, remediation diff, status) and `RELEASE_NOTES.md` (semantic summary: verified schemas, resolved dependency alerts, regression results) |
| **Output** | `security/audit-results.sarif`, `RELEASE_NOTES.md` |
| **Gate** | SARIF output should validate against the 2.1.0 JSON schema before being considered complete |

## Phase 8 — Gate Decision

| | |
|---|---|
| **Interactive path** | Artifacts and findings are presented to the developer in the IDE for review and manual merge decision |
| **Headless/CI path** | Bob Shell (`bob run`) exits **non-zero** if unresolved Critical/High findings or test regressions remain, halting pipeline progression; exits **0** and exports artifacts when all verifications pass |

---

## Sequence Summary (compact)

```
Init → Invoke → Ingest Spec → Plan (⏸ human approval) →
  ┌─ arch-auditor ─┐
  ├─ supply-sentinel ┤ (parallel, isolated) → aggregate findings
  └─ contract-guard ┘
→ [ Actor patch → Critic verify (isolated) ]* per finding →
→ full regression → SARIF + RELEASE_NOTES.md → gate (human or CI)
```

## Retry / Failure Semantics

- **Plan rejected by human**: coordinator returns to Plan Mode for revision; no code is touched.
- **Critic rejects patch**: loop returns to Actor with Critic's specific objection; bounded retry (recommended: 2 attempts) before escalating to human.
- **Full regression fails after all patches accepted**: run is marked failed; artifacts still generated but marked non-passing; CI exits non-zero.
- **Subagent tool failure** (e.g., can't parse a manifest): surfaced as a finding of type `tooling-error`, not silently dropped, so the coordinator's picture of coverage stays accurate.
