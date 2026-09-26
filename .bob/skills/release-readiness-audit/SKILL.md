---
name: release-readiness-audit
description: Executes an autonomous multi-agent release readiness audit. Use when evaluating a release candidate branch against architecture specs and security standards.
---

# Release Readiness Verification Skill

Execute this sequential procedure to validate the active release branch:

## 1. Specification Ingestion & Policy Extraction (Plan Mode)
- Ingest architectural specifications from `docs/architecture/` using Docling.
- Identify API contracts, database constraints, and compliance requirements.
- Construct an implementation plan and record it in `plans/release-readiness-plan.md`.
- **Stop and wait for explicit human confirmation before proceeding.**

## 2. Parallel Subagent Audit (Agent Mode)
Spawn three parallel subagents to analyze the repository:
- **Subagent 1** (`arch-auditor`, explore): scan `src/db/` for database schema drift and missing column indexes against the ingested spec.
- **Subagent 2** (`supply-sentinel`, explore): audit `requirements.txt` for outdated packages and critical CVE vulnerabilities (CVSS > 7.0).
- **Subagent 3** (`contract-guard`, general): verify all endpoints in `src/api/` against the ingested schema contracts.

Aggregate each subagent's structured finding summary into a single findings list; do not surface raw subagent tool logs in the parent session.

## 3. Actor-Critic Remediation
For all detected High or Critical findings:
- In Agent Mode, generate the minimal code patch complying with `.bob/rules/security.md` (Actor).
- Spawn an independent Critic subagent with `fork_context: false` to validate the patch against `.bob/rules/security.md` and OWASP ASVS Level 1 standards. The Critic must not receive the Actor's reasoning trace.
- On Critic rejection, return to the Actor step with the Critic's specific objection (bounded to 2 retries per finding, then escalate to human review).

## 4. Validation & Reporting
- Execute the regression test suite: `pytest tests/ -v`.
- Compile all findings into a SARIF 2.1.0 report saved to `security/audit-results.sarif`.
- Generate a semantic release summary in `RELEASE_NOTES.md`.
- If invoked headlessly (`bob run`), exit non-zero if any Critical/High finding remains unresolved or any test fails; otherwise exit 0.
