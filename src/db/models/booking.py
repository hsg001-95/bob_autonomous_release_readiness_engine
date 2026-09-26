import sqlite3
from datetime import date

DB_PATH = "galaxium.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_bookings_by_user(user_id: int):
    """Return all bookings for the given user using parameterised binding (RFC-042 §2.2)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookings WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def create_booking(user_id: int, flight_id: int, departure_date: date, seat_class: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bookings (user_id, flight_id, departure_date, seat_class) "
        "VALUES (?, ?, ?, ?)",
        (user_id, flight_id, str(departure_date), seat_class),
    )
    conn.commit()
    conn.close()


def get_booking_by_id(booking_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    # COMPLIANT reference example (kept for contrast)
    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    conn.close()
    return row
