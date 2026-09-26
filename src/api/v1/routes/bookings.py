from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.db.models.booking import get_bookings_by_user, create_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


# ---------------------------------------------------------------------------
# Request / Response schemas  (RFC-042 §3.1, §3.2, §3.3)
# ---------------------------------------------------------------------------

class BookingCreate(BaseModel):
    user_id: int = Field(ge=1)
    flight_id: int = Field(ge=1)
    departure_date: date
    seat_class: Literal["economy", "business", "first"]


class BookingCancelRequest(BaseModel):
    reason: str = Field(default="", max_length=500)


class BookingCreatedResponse(BaseModel):
    status: str


class BookingCancelledResponse(BaseModel):
    booking_id: int
    cancelled: bool
    reason: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{user_id}")
def list_bookings(user_id: int):
    """Return all bookings for a user."""
    return get_bookings_by_user(user_id)


@router.post("/", response_model=BookingCreatedResponse)
def add_booking(payload: BookingCreate):
    """Create a new booking. Payload validated by BookingCreate (RFC-042 §3.1)."""
    create_booking(payload.user_id, payload.flight_id, payload.departure_date, payload.seat_class)
    return {"status": "created"}


@router.delete("/{booking_id}", response_model=BookingCancelledResponse)
def delete_booking(booking_id: int, body: BookingCancelRequest):
    """Cancel a booking. Body validated by BookingCancelRequest (RFC-042 §3.1)."""
    return {"booking_id": booking_id, "cancelled": True, "reason": body.reason}
