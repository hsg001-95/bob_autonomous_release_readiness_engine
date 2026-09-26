# RFC-042: Booking Service v2 — Architecture Specification

**Status:** Approved  
**Version:** 2.0.0  
**Date:** 2024-01-15  
**Owner:** Platform Engineering

---

## 1. Overview

This document is the immutable baseline specification for the Galaxium Travels Booking Service v2. All implementation code in `src/` must conform to the requirements stated here. If a discrepancy is found between code and this specification, the code must be corrected — this document is not subject to reinterpretation.

---

## 2. Database Indexing Requirements

### 2.1 Mandatory Indexes

All database queries against the `bookings` table **must** have corresponding indexes to guarantee sub-10 ms P99 latency at scale.

| Table     | Column(s)                  | Index Type  | Rationale                              |
|-----------|----------------------------|-------------|----------------------------------------|
| bookings  | `user_id`                  | B-Tree      | Primary filter for user-scoped queries |
| bookings  | `departure_date`           | B-Tree      | Range scans for availability windows   |
| bookings  | `status`                   | B-Tree      | Filtering by booking lifecycle state   |
| bookings  | `(user_id, departure_date)`| Composite   | Compound query optimisation            |

### 2.2 Query Safety Rules

- **All SQL queries MUST use parameterised statements.** String-concatenated or f-string-interpolated SQL is forbidden without exception. Violations are treated as critical security defects (SQL injection surface).
- Raw `sqlite3` cursor usage must go through a helper that enforces parameter binding; direct `.execute(f"... {var}")` patterns are non-compliant.

---

## 3. Pydantic Route Validation Requirements

### 3.1 Request Payload Validation

Every API route that accepts a request body **must** declare a Pydantic `BaseModel` schema as its sole payload parameter. FastAPI dependency injection must be used; manual `request.json()` parsing or `dict` annotations are non-compliant.

```python
# COMPLIANT
class BookingCreate(BaseModel):
    user_id: int
    flight_id: int
    departure_date: date
    seat_class: Literal["economy", "business", "first"]

@router.post("/bookings")
def create_booking(payload: BookingCreate):
    ...
```

```python
# NON-COMPLIANT — forbidden
@router.post("/bookings")
def create_booking(payload: dict):
    ...
```

### 3.2 Field Constraints

All Pydantic models used in route schemas must declare explicit field constraints:

- String fields: `min_length`, `max_length`
- Numeric fields: `ge` / `le` bounds where a domain constraint exists
- Date fields: must be validated to reject past dates on creation endpoints
- Enum fields: must use `Literal` or `Enum` types — bare `str` is insufficient

### 3.3 Response Schemas

All routes must declare an explicit `response_model`. Routes returning `Any` or omitting `response_model` are non-compliant.

---

## 4. Dependency Rules

### 4.1 Vulnerability Policy

- No direct or transitive dependency may carry a CVSS base score **> 7.0** in a known CVE without an approved remediation ticket.
- `requirements.txt` must pin all dependencies to an exact version (`==`). Unpinned ranges (`>=`, `~=`) are non-compliant for production builds.
- The dependency manifest must be audited via `pip-audit` or `safety check` before every release candidate cut.

### 4.2 Approved Core Dependencies (v2 Baseline)

| Package       | Required Version | Notes                                  |
|---------------|-----------------|----------------------------------------|
| fastapi       | `>=0.100.0`     | Minimum for Pydantic v2 compatibility  |
| pydantic      | `>=2.0.0`       | v2 required; v1 is EOL                 |
| uvicorn       | `>=0.23.0`      | ASGI server                            |
| sqlalchemy    | `>=2.0.0`       | ORM; raw sqlite3 usage must be audited |
| python-jose   | `>=3.3.0`       | JWT; must not be pinned below 3.3.0    |

### 4.3 Forbidden Packages

The following packages are banned due to unpatched CVEs or abandonment:

| Package          | Reason                                           |
|------------------|--------------------------------------------------|
| `pyyaml < 6.0`   | CVE-2017-18342 — arbitrary code execution        |
| `cryptography < 41.0` | Multiple high-severity CVEs                 |
| `requests < 2.31.0`   | CVE-2023-32681 — proxy header leak          |

---

## 5. Compliance Verification

The CI pipeline must run the following checks before merge to `main`:

1. `pytest tests/` — full test suite must pass with zero failures.
2. `pip-audit -r requirements.txt` — zero findings with CVSS > 7.0.
3. Static analysis must flag any `.execute(` call not using `?` or `:name` placeholders.
4. All FastAPI route functions must resolve to a Pydantic model annotation; `dict` payloads fail the check.

Non-conformances discovered post-merge are treated as **P0 incidents**.
