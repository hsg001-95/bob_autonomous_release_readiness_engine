# Technical Requirements Document (TRD)
## Autonomous Release Readiness and Governance Engine (RRE)

---

## 1. Purpose

This TRD specifies the technical implementation details required to build the RRE prototype on IBM Bob 2.0 against the reference target `galaxium-travels`, including file layout, interfaces, data formats, and the standard-library-only constraint for any project-authored tooling.

## 2. Reference Target System

**galaxium-travels** — a multi-tier commercial booking application:
- Backend: FastAPI (Python) + a Node.js service
- Data store: SQLite, accessed asynchronously
- Structured REST endpoints under `src/api/v1/`
- MCP (Model Context Protocol) tooling integration points

## 3. Repository Layout (project-authored assets)

```
.
├── AGENTS.md
├── .bobignore
├── .bob/
│   ├── rules/
│   │   └── security.md
│   └── skills/
│       └── release-readiness-audit/
│           └── SKILL.md
├── docs/
│   └── architecture/
│       └── rfc-042-booking-v2.pdf        # or .md — the ingested spec
├── plans/
│   └── release-readiness-plan.md         # generated at runtime
├── security/
│   └── audit-results.sarif               # generated at runtime
├── RELEASE_NOTES.md                       # generated at runtime
├── src/
│   ├── api/v1/routes/
│   ├── db/
│   │   └── models/
│   └── ...
├── requirements.txt
└── tests/
```

## 4. Interface Specifications

### 4.1 Skill Invocation (Interactive)
```
/release-readiness-audit Ingest @<path-to-spec> and evaluate whether the
active release candidate satisfies architectural, dependency, and security
policies.
```

### 4.2 Skill Invocation (Headless / CI)
```bash
bob run --skill release-readiness-audit \
        --mode Agent \
        --context "docs/architecture/rfc-042-booking-v2.pdf" \
        --auto-approve "read,test" \
        "Validate release candidate branch for production readiness. Fail build if critical findings persist."
```
Exit codes: `0` = all verifications passed; non-zero = unresolved Critical/High findings or test regressions.

### 4.3 Subagent Contract
Each spawned subagent must return a structured summary object (conceptually, not necessarily a literal schema enforced by the platform) containing at minimum:
```
{
  "subagent": "arch-auditor | supply-sentinel | contract-guard",
  "findings": [
    {
      "id": "string, stable within a run",
      "severity": "info | low | medium | high | critical",
      "location": "file path + line/range where applicable",
      "description": "human-readable finding",
      "rule_ref": "reference into the spec constraint or .bob/rules/security.md"
    }
  ],
  "tool_calls": integer,
  "tokens_used": integer,
  "elapsed_ms": integer
}
```

## 5. SARIF Output Requirements

- Must conform to **SARIF 2.1.0** JSON schema.
- Each `result` object must map to exactly one finding from Phase 4/5 of the workflow.
- `ruleId` must reference either the ingested spec constraint ID or a rule from `.bob/rules/security.md`.
- `level` must map severity (`critical`/`high` → `error`, `medium` → `warning`, `low`/`info` → `note`).
- Where a finding was remediated, the result must include the remediation diff reference and the Critic's pass confirmation (e.g., via SARIF `properties` bag, since SARIF 2.1.0 does not have a first-class "remediation" object).
- Output path: `security/audit-results.sarif`.

## 6. Standard-Library-Only Constraint (Implementation Rule)

Any tooling authored *by this project* (as opposed to native Bob 2.0 platform capabilities) must use the Python standard library wherever it is sufficient. Concretely:

| Task | Standard-library approach |
|---|---|
| SARIF JSON assembly | `json` module — build the SARIF document as nested `dict`/`list` and `json.dump`; no schema/serialization library required |
| SARIF schema validation | Hand-rolled structural checks using `json` + basic assertions, or `jsonschema` **only if** a third-party validator is explicitly desired for rigor (documented as the one justified exception) |
| Dependency manifest parsing (`requirements.txt`) | Plain text parsing with `re` / `str` methods — `requirements.txt` is line-oriented and does not require a package-management library to read |
| CVE/CVSS lookups | If an external vulnerability database call is needed, use `urllib.request` for HTTP rather than `requests`, to keep the tooling dependency-free |
| Test execution | Shell out to `pytest` via `subprocess` (pytest itself is a project dependency of the *target* repo, not of RRE's own tooling) |
| Report templating (`RELEASE_NOTES.md`) | `string.Template` or plain f-strings — no templating engine required |
| File system scanning | `os` / `pathlib` |
| Config parsing (`.bobignore`, front matter in `SKILL.md`) | `re`/manual parsing for `.gitignore`-style syntax; simple YAML front matter can be hand-parsed line-by-line to avoid a `pyyaml` dependency, given the front matter here is flat key/value |

**Explicit exception**: Docling (document parsing) is a native IBM Bob 2.0 platform capability, invoked by the agent, not a library this project imports and maintains — it is out of scope for the standard-library constraint.

## 6a. Secrets-Sentinel Implementation Spec

Pure standard library (`re`, `math`, `os`, `pathlib`):

1. **Pattern pass**: match against a small set of high-confidence regexes for well-known key formats (e.g. `AKIA[0-9A-Z]{16}` for AWS access keys, `sk-[A-Za-z0-9]{20,}`-style OpenAI/Anthropic-style keys, generic `-----BEGIN PRIVATE KEY-----` blocks, `postgres://user:pass@host` connection strings with an embedded password).
2. **Entropy pass** (catches unknown/custom token formats): for any string literal assigned to a variable whose name matches `(?i)(key|secret|token|password|pwd|credential)`, compute Shannon entropy over the string; flag if entropy exceeds a threshold (commonly ~4.0 bits/char for base64-like strings of length ≥ 16) *and* the string is not present in a recognized placeholder list (`changeme`, `xxx`, `<your-key-here>`, etc.).
3. Every match is reported at `critical` severity per R9, with file + line, regardless of what patch/finding triggered the scan (whole-repo scope).
4. False-positive control: maintain a small allowlist file (`security/secrets-allowlist.txt`) of known-safe fixture values (e.g. a test-only dummy key used intentionally in `tests/`) so the demo doesn't self-flag its own test fixtures.

## 6b. SBOM Generation Spec

Extends `supply-sentinel`. Pure standard library (`importlib.metadata`, `json`):

- Enumerate installed distributions via `importlib.metadata.distributions()`.
- For each, record name, version, and (where available) declared license metadata.
- Emit as a CycloneDX-*lite* JSON document (a hand-built subset of the real CycloneDX schema — full schema compliance is not required for the hackathon scope, but the field names should match CycloneDX so the artifact is recognizable/upgradable): `{"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{"type": "library", "name": ..., "version": ..., "licenses": [...]}]}`.
- Output path: `sbom/bom.json`.
- Cross-reference against `requirements.txt` per R10: any installed component with no corresponding `requirements.txt` entry (or vice versa) is a `medium` finding.

## 6c. Release Confidence Score Spec

A single 0–100 number computed from data already produced by the pipeline — not a new data source:

```
score = 100
      - 25 * (unresolved_critical_findings > 0)
      - 15 * min(unresolved_high_findings, 3)
      -  5 * min(unresolved_medium_findings, 4)
      - 20 * (full_regression_suite_failed)
      - 10 * (any_rule_R1_to_R10_uncovered_by_this_run)
score = max(score, 0)
```

This is intentionally a simple, transparent, auditable formula (not a model call) — standard library arithmetic only. It must be computed the same way every run so it's comparable across releases, and the formula itself should be printed alongside the number in `RELEASE_NOTES.md` so it's never a black box to a reviewer.

## 7. Data Model — Findings

| Field | Type | Notes |
|---|---|---|
| `id` | string | stable within a run, e.g. `db-001`, `dep-001`, `api-001` |
| `category` | enum | `schema-drift` \| `dependency` \| `contract-drift` \| `tooling-error` |
| `severity` | enum | `critical` \| `high` \| `medium` \| `low` \| `info` |
| `location` | string | file path, optionally `:line` or `:line-range` |
| `description` | string | human-readable |
| `spec_ref` | string | clause/section in the ingested spec this violates |
| `remediation_status` | enum | `unresolved` \| `patched-pending-critic` \| `patched-verified` \| `escalated` |

## 8. Rule Book Requirements (feeds `.bob/rules/security.md`)

Minimum enforceable rules for the Actor/Critic loop on the reference target:
1. **Query parameterization** — no string-concatenated SQL; SQLAlchemy ORM or parameterized statements only.
2. **Input validation** — all FastAPI route handlers must validate payloads via explicit Pydantic models with strict typing and boundary constraints (no raw `dict` payloads).
3. **Exception handling** — database/external-service exceptions caught at boundary layers; internal stack traces must not be returned in API responses.
4. **Dependency hygiene** — no transitive dependency with a CVSS score > 7.0 left unresolved.
5. **API backward compatibility** — removing/modifying existing `src/api/v1` attributes requires deprecation aliasing, not a breaking change.

## 9. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Context isolation | Coordinator must never receive raw subagent tool logs, only structured summaries |
| Critic independence | `fork_context: false` enforced for all Critic spawns — verified by confirming the Critic's available context does not include the Actor's transcript |
| Determinism of gating | Given the same repo state + spec + rule book, the pass/fail gate decision must be reproducible |
| Auditability | Every finding in the SARIF output must be traceable to the subagent run and spec clause that produced it |
| Portability | The `.bob/` config and skill must run unmodified against any repo matching the assumed layout (FastAPI-style `src/api`, `src/db`, `requirements.txt`), not hardcoded to `galaxium-travels` internals beyond the demo |

## 10. Testing Strategy

- **Seeded-finding tests**: the demo repo ships with a known, fixed set of injected non-conformances (see demo repo README). A successful run must detect 100% of seeded findings with zero false positives on the seeded set — this is the primary correctness check for the hackathon demo, and the only metric it is fair to report precisely.
- **Critic isolation test**: confirm the Critic subagent cannot reference anything from the Actor's session (spot-check via a prompt that would only be answerable if the transcript leaked).
- **SARIF validity test**: parse the emitted `audit-results.sarif` with the `json` module and check required top-level keys (`$schema`, `version`, `runs`) are present and well-formed.
- **CI exit-code test**: run `bob run` headlessly against a branch with a known unresolved Critical finding and confirm non-zero exit.

## 11. Out of Scope for This TRD

- Full OWASP ASVS Level 2/3 coverage (Level 1 only, per PRD).
- Multi-repo / multi-service orchestration beyond the single reference target.
- Persistent historical trend reporting across releases (each run is self-contained).
