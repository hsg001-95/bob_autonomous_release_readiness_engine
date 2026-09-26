# Release Readiness Verification Plan — RFC-042 Booking API v2

## Meta

| Field           | Value                                              |
|-----------------|----------------------------------------------------|
| Target Spec     | `docs/architecture/rfc-042-booking-v2.md`          |
| Spec Version    | RFC-042 v2.0.0 (immutable baseline)                |
| Scope           | Galaxium Travels — FastAPI + SQLite booking service |
| Plan Status     | ✅ Human Approval Gate passed; ready for automated execution |
| Authored By     | Coordinator (Plan Mode)                            |

---

## Verification Streams

### Stream 1 — Database Schema & Query Safety
**Subagent:** `arch-auditor`  
**Rule:** R1 — Query Parameterization  
**Spec Ref:** RFC-042 §2.1, §2.2

Inspect `src/db/models/` for:
- Any SQL query constructed by f-string interpolation or string concatenation (violation)
- All `cursor.execute()` calls must use `?` positional or `:name` named placeholders with a params tuple
- Verify mandatory indexes are present or documented: `user_id`, `departure_date`, `status`, and the composite `(user_id, departure_date, status)`

**Pass Criteria:** Zero raw string-interpolated SQL. All `execute()` calls carry a non-`None` params argument.

---

### Stream 2 — Dependency Hygiene
**Subagent:** `supply-sentinel`  
**Rule:** R4 — Dependency Hygiene  
**Spec Ref:** RFC-042 §4.1, §4.2, §4.3

Audit `requirements.txt` for:
- Every entry must be pinned with `==` (no `>=`, `~=`, or unpinned)
- No direct or transitive dependency with CVSS base score > 7.0
- Explicitly forbidden package check: `pyyaml < 6.0` (CVE-2017-18342, CVSS 9.8)
- Verify approved core versions: `fastapi >=0.100.0`, `pydantic >=2.0.0`, `uvicorn >=0.23.0`, `sqlalchemy >=2.0.0`

**Pass Criteria:** All dependencies pinned. No forbidden or high-severity CVE packages present.

---

### Stream 3 — API Contract Conformance
**Subagent:** `contract-guard`  
**Rule:** R2 — Input Validation  
**Spec Ref:** RFC-042 §3.1, §3.2, §3.3

Check `src/api/v1/routes/bookings.py` for:
- `POST /bookings/` must accept a `BookingCreate(BaseModel)` parameter with field constraints (`ge=1`, `Literal` seat class enum, `date` type)
- `DELETE /bookings/{id}` must accept a `BookingCancelRequest(BaseModel)` parameter
- Both mutating routes must declare `response_model=`
- No route may accept an untyped `dict`, bare `Request`, or call `request.json()` directly
- Pydantic validation must cause HTTP 422 on malformed payloads

**Pass Criteria:** All routes use named Pydantic model parameters. `response_model` declared on POST and DELETE. 422 returned on invalid payloads.

---

### Stream 4 — Regression & Non-Zero Exit Testing
**Actor:** Coordinator (Agent Mode)  
**Rule:** R6 — Test Regression  
**Spec Ref:** RFC-042 §5

Execute and verify:
1. `pytest tests/ -v` — full regression suite must exit 0 with **10 passed, 0 failed**
2. Governance gate probe — deliberately inject a schema violation and confirm `pytest` exits non-zero, then restore the workspace and confirm exit 0

**Pass Criteria:** `pytest` exits 0 on the clean codebase. Non-zero exit confirmed when a violation is injected. Workspace restored to clean state after probe.

---

## Verification Stream Summary (Final Status)

| Stream | Subagent | Rule Target | Scope / Target Files | Status |
|---|---|---|---|---|
| **1 — DB Schema & Query Safety** | `arch-auditor` | R1 | `src/db/models/` | ✅ Parameterized bindings verified (F-1a, F-1b) |
| **2 — Supply Chain & Provenance** | `supply-sentinel` | R4, R10 | `requirements.txt` & environment | ✅ `pyyaml==6.0.1` + 103 SBOM components tracked |
| **3 — API Contract Conformance** | `contract-guard` | R2 | `src/api/v1/routes/` | ✅ Pydantic models validated (F-2a, F-2b) |
| **4 — Secrets & Credentials** | `secrets-sentinel` | R9 | Repository-wide | ✅ 0 findings (exit code 0) |


## Subagent Execution Policy

- All three audit subagents (Streams 1–3) run **in parallel** with isolated contexts (`fork_context: false` unless prior conversation context is explicitly required)
- Critic subagents validating Actor patches **must** be spawned with `fork_context: false`
- Each subagent returns a structured findings summary: `finding_id`, `severity`, `location`, `description`, `rule_ref`, `remediation_status`
- Raw subagent logs are **not** surfaced to the coordinator; only the structured summary is aggregated

---

## Gate Conditions

| Condition                                      | Required Outcome      |
|------------------------------------------------|-----------------------|
| Stream 1 — SQL parameterization                | 0 violations          |
| Stream 2 — Dependency CVE scan                 | 0 CVSS > 7.0 packages |
| Stream 3 — Pydantic contract conformance       | 0 unvalidated routes  |
| Stream 4 — Regression suite                    | 10 passed, 0 failed   |
| Stream 4 — Non-zero exit probe                 | exit 1 on violation   |
| SARIF 2.1.0 artifact                           | Valid, all findings recorded |

**Release Decision:** All gate conditions must be satisfied for `RELEASE_APPROVED`. Any Critical or High open finding blocks release and triggers a non-zero exit in headless/CI mode.

---

## Output Artifacts

| Artifact                          | Path                              |
|-----------------------------------|-----------------------------------|
| SARIF 2.1.0 compliance report     | `security/audit-results.sarif`    |
| Release notes                     | `RELEASE_NOTES.md`                |
| This verification plan            | `plans/release-readiness-plan.md` |
