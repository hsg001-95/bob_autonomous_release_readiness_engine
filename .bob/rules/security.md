# Rule Book — `.bob/rules/security.md`
## Enterprise Security and API Verification Rules

This file is loaded across all conversations/subagent sessions involved in the release-readiness audit. It governs both the **Actor** (what it is allowed to generate) and the **Critic** (what it checks against). It is intentionally short and concrete — every rule here must be independently checkable by an isolated Critic with no access to Actor reasoning.

---

## R1 — Query Parameterization
Database operations must use SQLAlchemy ORM constructs or parameterized statements. String concatenation or f-string interpolation into SQL is strictly prohibited, with no exceptions.

- ✅ `session.query(Booking).filter(Booking.passenger_uuid == uuid)`
- ✅ `conn.execute(text("SELECT * FROM bookings WHERE id = :id"), {"id": booking_id})`
- ❌ `f"SELECT * FROM bookings WHERE id = {booking_id}"`

**Critic check**: `grep`/AST scan for string-formatted SQL literals in any file touched by the patch; fail if found.

## R2 — Input Validation
All FastAPI route handlers must validate input payloads using explicit Pydantic schemas with strict typing and defined boundary constraints (e.g., `max_length`, numeric ranges, enum constraints where applicable). Untyped `dict` or `Any`-typed request bodies are not permitted on any route that accepts external input.

**Critic check**: every route handler signature touched by the patch must reference a Pydantic `BaseModel` subclass for its request body; run `flake8`/type-check as a secondary signal.

## R3 — Exception Handling
Database and external-service exceptions must be caught at boundary layers (route handlers or a shared middleware). Internal stack traces, ORM error text, or file paths must never be returned in an API response body. Client-facing errors must be generic, logged errors must be detailed.

**Critic check**: no bare `except Exception as e: return {"error": str(e)}` patterns returning raw exception text to the client.

## R4 — Dependency Hygiene
Transitive and direct dependencies with a CVSS score exceeding 7.0 must be remediated (upgraded to the minimum version that resolves the CVE, or replaced if no fix exists). Version pins must not be silently removed to "fix" the issue.

**Critic check**: re-run the dependency scan on the patched manifest; fail if any dependency still exceeds the threshold.

## R5 — API Backward Compatibility
Modifying or removing an existing attribute in an `src/api/v1` route's request or response schema requires deprecation aliasing (the old field remains accepted/returned alongside the new one for at least one release cycle) rather than a breaking change.

**Critic check**: diff the route's Pydantic schema before/after the patch; any removed field without a corresponding alias/deprecation marker fails.

## R6 — Test Regression
No patch is accepted without the relevant test subset passing. The Critic runs the targeted tests for any file it touched, and the full suite is re-run once per audit before final sign-off (see Workflow Phase 6).

**Critic check**: `pytest <relevant path> -v` exit code must be 0.

## R7 — Scope Discipline
The Actor must generate the *minimal* diff that resolves the specific finding it was assigned. Opportunistic refactors, style-only changes, or fixes to unrelated findings in the same patch are not permitted — each finding gets its own patch and its own Critic review.

**Critic check**: diff size/file-touch count should map 1:1 to the finding being addressed; unrelated file changes are flagged and rejected.

## R8 — Rule Precedence
If a finding conflicts with these rules in a way that has no clean resolution (e.g., the spec appears to require something R1–R7 forbid), the Actor must **not** silently choose one; it must record the conflict as an `escalated` finding for human review rather than generate a patch.

---

### Independence Requirement (applies to how this file is used, not a rule on code)
The Critic subagent must be spawned with `fork_context: false` and must receive **only**:
1. The files modified by the Actor's patch
2. This rule book

It must not receive the Actor's prompt history, planning notes, or reasoning trace. This is what makes R1–R8 an *independent* check rather than the same reasoning re-affirming itself.
