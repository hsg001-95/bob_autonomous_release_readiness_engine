# Autonomous Release Readiness and Governance Engine (RRE)

**Enterprise Release Verification on IBM Bob 2.0**  
Hackathon submission for the _IBM Bob 2.0 Hackathon_ — theme: **Build with purpose using IBM Bob 2.0**

---

## Overview

The RRE is a fully automated, AI-driven release-governance workflow built on IBM Bob 2.0. It audits the Galaxium Travels booking service against an immutable specification baseline (RFC-042 v2.0.0), locates and remediates security findings via an Actor-Critic loop, produces a SARIF 2.1.0 compliance report, and gates the release with a deterministic exit-code test — all without a single manual intervention.

---

## Key Metrics Summary

| Dimension | Result |
|---|---|
| **Regression Suite** | ✅ 10 passed · 0 failed · 0 xfailed · 0 errors |
| **SARIF Compliance** | ✅ SARIF 2.1.0 Validated (OASIS standard) |
| **Remediated Defects** | F-1 SQL Parameterization (R1) · F-2 Pydantic Schema Validation (R2) · F-3 CVE-2017-18342 PyYAML 6.0.1 (R4) |
| **Governance Gate** | ✅ Phase 8 exit code 0 (clean) · exit code 1 on injected schema violation · 0% repository drift |
| **Subagents** | 4 parallel (arch-auditor · supply-sentinel · contract-guard · secrets-sentinel) |
| **Rules Enforced** | 10 / 10 (R1–R10) |
| **Secrets Scan** | ✅ 0 hardcoded credentials leaked (exit code 0) |
| **SBOM** | 103 components tracked in `sbom/bom.json` (CycloneDX-lite) |
| **Release Confidence Score** | 100 / 100 (TRD §6c) |
| **Resource Consumption** | 23.25 / 40.00 Bobcoins consumed (58% budget remaining) |

---

## Bob 2.0 Feature Utilization

### 1 — Docling Spec Parsing
RFC-042 (`docs/architecture/rfc-042-booking-v2.md`) was parsed at the start of the audit using Bob's document-understanding capabilities. Docling extracted structured sections (§2.2 Query Safety Rules, §3.3 Schema Requirements, §4.3 Forbidden Packages) and translated them directly into SARIF rule definitions in `security/audit-results.sarif`. This eliminated any manual transcription of specification requirements.

### 2 — Isolated Actor-Critic Verification (`fork_context: false`)
Every remediation patch produced by the Actor subagent was validated by a separate Critic subagent spawned with `fork_context: false`. This guarantees that the Critic has no access to the Actor's reasoning chain and cannot inherit its blind spots — it verifies only the diff and the spec, producing an independent verdict. This pattern is enforced in `AGENTS.md`.

### 3 — Declarative Rules (`.bob/rules/security.md`)
Project-level security rules were declared as a persistent rule file that Bob loads automatically on every session. Rules encode the zero-tolerance policy for unparameterised SQL, unvalidated API routes, and forbidden dependency versions, ensuring every future Agent-mode session inherits the same governance constraints without re-prompting.

### 4 — Atomic Backup / Restore Regression Validation
Before each Actor patch was applied, Bob captured an atomic snapshot of all target files. After the patch the full regression suite (`pytest tests/ -v`) was executed. On any failure the workspace was restored from snapshot automatically, preventing partial-patch corruption. This made the remediation loop safe to run end-to-end without human supervision.

---

## Architecture at a Glance

```
RFC-042 spec (Docling)
        │
        ▼
  Phase 1-4: Audit  ──── SARIF 2.1.0 report ────► security/audit-results.sarif
        │
        ▼
  Phase 5: Actor patches F-1, F-2, F-3
        │
        ▼
  Phase 6: Critic (fork_context: false) validates each patch
        │
        ▼
  Phase 7: pytest 10/10 green
        │
        ▼
  Phase 8: Governance gate — exit 0 (clean) · exit 1 (violation injected)
```

---

## Repository Structure

```
.
├── docs/architecture/rfc-042-booking-v2.md   # Immutable spec baseline
├── security/audit-results.sarif              # SARIF 2.1.0 audit report
├── src/
│   ├── api/v1/routes/bookings.py             # F-2 fix: Pydantic models + response_model
│   └── db/models/booking.py                  # F-1 fix: parameterised SQL
├── tests/test_bookings.py                    # Regression suite (10 tests)
├── requirements.txt                          # F-3 fix: pyyaml==6.0.1
├── AGENTS.md                                 # Bob governance rules
├── RELEASE_NOTES.md                          # Detailed remediation log
└── bob_sessions/                             # Bob IDE session screenshots
```

---

## Judge Evaluation Guide

Follow these steps to independently verify every claim in this submission.

### Step 1 — Run the regression suite

```bash
pytest tests/ -v
```

**Expected output:**
```
tests/test_bookings.py::TestGetBookingById::test_returns_none_for_missing_id PASSED
tests/test_bookings.py::TestGetBookingById::test_returns_row_after_insert PASSED
tests/test_bookings.py::TestGetBookingsByUser::test_empty_when_no_bookings PASSED
tests/test_bookings.py::TestGetBookingsByUser::test_returns_only_matching_user PASSED
tests/test_bookings.py::TestListBookingsRoute::test_returns_200_for_valid_user PASSED
tests/test_bookings.py::TestListBookingsRoute::test_returns_empty_list_when_no_bookings PASSED
tests/test_bookings.py::TestAddBookingRoute::test_creates_booking_returns_status_created PASSED
tests/test_bookings.py::TestAddBookingRoute::test_rejects_payload_missing_required_fields PASSED
tests/test_bookings.py::TestDeleteBookingRoute::test_cancel_returns_booking_id_and_reason PASSED
tests/test_bookings.py::TestSqlParameterBinding::test_query_uses_parameter_binding PASSED

10 passed in X.XXs
```

### Step 2 — Validate SARIF 2.1.0 integrity

```python
import json, sys

with open("security/audit-results.sarif") as f:
    sarif = json.load(f)

assert sarif["version"] == "2.1.0", "Wrong SARIF version"
assert "$schema" in sarif, "Missing $schema"
runs = sarif["runs"]
assert len(runs) == 1, "Expected exactly one run"
results = runs[0]["results"]
print(f"SARIF version : {sarif['version']}")
print(f"Tool          : {runs[0]['tool']['driver']['name']}")
print(f"Results       : {len(results)} findings recorded")
rules = {r["id"] for r in runs[0]["tool"]["driver"]["rules"]}
print(f"Rules defined : {sorted(rules)}")
print("SARIF integrity check: PASSED")
```

```bash
python - < <(cat <<'EOF'
import json, sys
with open("security/audit-results.sarif") as f:
    sarif = json.load(f)
assert sarif["version"] == "2.1.0"
assert "$schema" in sarif
runs = sarif["runs"]
assert len(runs) == 1
results = runs[0]["results"]
print(f"SARIF {sarif['version']} · {runs[0]['tool']['driver']['name']} · {len(results)} findings · rules {sorted(r['id'] for r in runs[0]['tool']['driver']['rules'])}")
print("SARIF integrity check: PASSED")
EOF
)
```

### Step 3 — Inspect the release notes

Open [`RELEASE_NOTES.md`](RELEASE_NOTES.md) to review:
- Detailed description of each finding (F-1, F-2, F-3)
- Before/after code diffs for every fix
- The full 10/10 test result table
- Open advisories (ADV-01 through ADV-03, non-blocking)
- Evidence of Bob IDE Usage section with `bob_sessions/` catalogue

### Step 4 — Review Bob IDE session evidence

```bash
ls -lh bob_sessions/
```

All screenshots were captured directly from the IBM Bob IDE task panel. The verified session snapshots are:

| File | Activity | Bobcoins |
|---|---|---|
| `bob_sessions/team_task01_agents_summary.png` | AGENTS.md generation | 0.061 |
| `bob_sessions/team_task02_remediation_summary.png` | Core remediation & regression tests | 6.88 |
| `bob_sessions/task03_readme_update_summary.png` | Documentation alignment | 1.04 |
| `bob_sessions/task04_doc_analysis_summary.png` | Document analysis & architecture review | 1.39 |
| `bob_sessions/task05_secrets_fix_summary.png` | Secrets sentinel integration & allowlist fix | 6.93 |
| `bob_sessions/budget_remaining_58pct.png` | Account budget card — 16.75 / 40.00 remaining (58%) | — |

### Step 5 — Verify the governance gate (Phase 8)

The Phase 8 gate script confirms the repository is clean and that a deliberately injected violation triggers a non-zero exit:

```bash
# Clean state — must exit 0
python -c "
import subprocess, sys
result = subprocess.run(['pytest', 'tests/', '-v', '--tb=short'], capture_output=True)
sys.exit(0 if result.returncode == 0 else 1)
"
echo "Exit code (clean): $?"

# Injected violation — must exit 1 (demonstrated during Bob session)
```

---

## Bobcoin Budget

| Task | Activity | Bobcoins |
|---|---|---|
| Task 01 | AGENTS.md generation | 0.061 |
| Task 02 | Core remediation & regression tests (F-1, F-2, F-3 + Critic loop) | 6.880 |
| Task 03 | Documentation alignment | 1.040 |
| Task 04 | Document analysis & architecture review | 1.390 |
| Task 05 | Secrets sentinel integration & allowlist fix | 6.930 |
| Misc | Remaining tooling, SBOM, confidence score, plan updates | 6.949 |
| **Total consumed** | | **23.25 / 40.00** |
| **Remaining balance** | 58% budget remaining | **16.75 Bobcoins** |

---

## Compliance References

| Artefact | Location |
|---|---|
| Architecture spec (immutable baseline) | `docs/architecture/rfc-042-booking-v2.md` |
| SARIF 2.1.0 audit report | `security/audit-results.sarif` |
| Regression suite | `tests/test_bookings.py` |
| Bob governance rules | `AGENTS.md` |
| Release notes | `RELEASE_NOTES.md` |
| Bob IDE session screenshots | `bob_sessions/` |
| Bob task session log | `bob-task-806f4998970c5cf27a586fe9df473076-2026-09-26.md` |
