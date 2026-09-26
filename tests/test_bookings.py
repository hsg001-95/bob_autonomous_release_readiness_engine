"""
tests/test_bookings.py

Basic test suite for the Galaxium Travels booking service.

Covers:
  - DB model helpers (in-memory SQLite)
  - FastAPI route behaviour via httpx AsyncClient / TestClient
  - Conformance probes that document the known non-conformances
    (marked xfail so the suite stays green while the bugs exist)
"""

import json
import sqlite3
import pytest
from datetime import date
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Shared in-memory DB URI so every thread sees the same data
_IN_MEMORY_URI = "file:test_db?mode=memory&cache=shared"


@pytest.fixture()
def db_conn():
    """
    Shared-cache in-memory SQLite connection.
    check_same_thread=False so FastAPI worker threads can reuse it.
    """
    conn = sqlite3.connect(_IN_MEMORY_URI, uri=True, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            flight_id     INTEGER NOT NULL,
            departure_date TEXT NOT NULL,
            seat_class    TEXT NOT NULL
        )
        """
    )
    conn.commit()
    yield conn
    conn.execute("DROP TABLE IF EXISTS bookings")
    conn.commit()
    conn.close()


@pytest.fixture()
def test_client(db_conn):
    """
    FastAPI TestClient with the bookings router mounted.
    Every get_connection() call returns a new handle to the same shared DB.
    """
    from src.api.v1.routes.bookings import router

    app = FastAPI()
    app.include_router(router)

    def _fake_get_connection():
        return sqlite3.connect(_IN_MEMORY_URI, uri=True, check_same_thread=False)

    with patch("src.db.models.booking.get_connection", side_effect=_fake_get_connection):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# DB model tests
# ---------------------------------------------------------------------------

def _shared_conn():
    return sqlite3.connect(_IN_MEMORY_URI, uri=True, check_same_thread=False)


class TestGetBookingById:
    def test_returns_none_for_missing_id(self, db_conn):
        with patch("src.db.models.booking.get_connection", side_effect=_shared_conn):
            from src.db.models.booking import get_booking_by_id
            result = get_booking_by_id(999)
        assert result is None

    def test_returns_row_after_insert(self, db_conn):
        db_conn.execute(
            "INSERT INTO bookings (user_id, flight_id, departure_date, seat_class) "
            "VALUES (1, 10, '2025-06-01', 'economy')"
        )
        db_conn.commit()
        with patch("src.db.models.booking.get_connection", side_effect=_shared_conn):
            from src.db.models.booking import get_booking_by_id
            row = get_booking_by_id(1)
        assert row is not None
        assert row[1] == 1   # user_id
        assert row[4] == "economy"


class TestGetBookingsByUser:
    def test_empty_when_no_bookings(self, db_conn):
        with patch("src.db.models.booking.get_connection", side_effect=_shared_conn):
            from src.db.models.booking import get_bookings_by_user
            rows = get_bookings_by_user(42)
        assert rows == []

    def test_returns_only_matching_user(self, db_conn):
        db_conn.executemany(
            "INSERT INTO bookings (user_id, flight_id, departure_date, seat_class) "
            "VALUES (?, ?, ?, ?)",
            [(1, 10, "2025-06-01", "economy"), (2, 11, "2025-07-01", "business")],
        )
        db_conn.commit()
        with patch("src.db.models.booking.get_connection",
                   side_effect=lambda: sqlite3.connect(_IN_MEMORY_URI, uri=True, check_same_thread=False)):
            from src.db.models.booking import get_bookings_by_user
            rows = get_bookings_by_user(1)
        assert len(rows) == 1
        assert rows[0][1] == 1


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------

class TestListBookingsRoute:
    def test_returns_200_for_valid_user(self, test_client):
        response = test_client.get("/bookings/1")
        assert response.status_code == 200

    def test_returns_empty_list_when_no_bookings(self, test_client):
        response = test_client.get("/bookings/99")
        assert response.status_code == 200
        assert response.json() == []


class TestAddBookingRoute:
    def test_creates_booking_returns_status_created(self, test_client):
        payload = {
            "user_id": 1,
            "flight_id": 10,
            "departure_date": "2025-08-01",
            "seat_class": "economy",
        }
        response = test_client.post("/bookings/", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "created"

    def test_rejects_payload_missing_required_fields(self, test_client):
        """Pydantic schema now enforces required fields — expects 422 (RFC-042 §3.1)."""
        response = test_client.post("/bookings/", json={"user_id": 1})
        assert response.status_code == 422


class TestDeleteBookingRoute:
    def test_cancel_returns_booking_id_and_reason(self, test_client):
        # Older httpx/Starlette TestClient does not support a body on .delete();
        # use the generic .request() method instead.
        response = test_client.request(
            "DELETE",
            "/bookings/5",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"reason": "changed plans"}),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["booking_id"] == 5
        assert body["cancelled"] is True
        assert body["reason"] == "changed plans"


# ---------------------------------------------------------------------------
# Conformance probes — document known non-conformances
# ---------------------------------------------------------------------------

class TestSqlParameterBinding:
    def test_query_uses_parameter_binding(self, db_conn):
        """
        get_bookings_by_user must call execute() with a params tuple (RFC-042 §2.2).

        sqlite3.Cursor is a C-extension type whose methods are immutable on Python 3.14+,
        so patch.object cannot wrap them directly. Instead, we inject a MagicMock cursor
        via a fake connection wrapper that records calls and delegates to a real cursor.
        """
        from unittest.mock import MagicMock, call as mock_call

        real_conn = sqlite3.connect(_IN_MEMORY_URI, uri=True, check_same_thread=False)
        real_cursor = real_conn.cursor()
        execute_calls = []

        # Wrapper that records calls then delegates to the real cursor.
        mock_cursor = MagicMock(wraps=real_cursor)
        mock_cursor.execute.side_effect = lambda sql, params=None: (
            execute_calls.append((sql, params)),
            real_cursor.execute(sql, params) if params is not None else real_cursor.execute(sql),
        )
        mock_cursor.fetchall.side_effect = real_cursor.fetchall

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close.return_value = None

        with patch("src.db.models.booking.get_connection", return_value=mock_conn):
            from src.db.models.booking import get_bookings_by_user
            get_bookings_by_user(1)

        real_conn.close()

        bookings_calls = [(sql, params) for sql, params in execute_calls if "bookings" in sql]
        assert bookings_calls, "execute() was never called with a bookings query"
        for sql, params in bookings_calls:
            assert params is not None and isinstance(params, (tuple, list)), (
                f"execute() called without parameter binding: {sql!r}"
            )
            assert "?" in sql or ":" in sql, (
                f"SQL does not contain a placeholder — possible string interpolation: {sql!r}"
            )
