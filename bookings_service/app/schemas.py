# bookings_service/app/schemas.py
from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .constants.service_periods import SERVICE_PERIODS

VALID_STATUSES = {"draft", "confirmed", "seated", "completed", "cancelled"}
VALID_ORDERING_MODES = {"group", "inperson"}
VALID_ATTENDEE_TYPES = {"member", "guest"}
VALID_RELATIONS = {"primary", "family", "guest"}


# ----------------------------
# Attendees
# ----------------------------
class AttendeeInput(BaseModel):
    type: str
    member_id: Optional[int] = None
    name: Optional[str] = None
    relation: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_ATTENDEE_TYPES:
            raise ValueError(f"type must be one of: {sorted(VALID_ATTENDEE_TYPES)}")
        return v

    @field_validator("relation")
    @classmethod
    def validate_relation(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_RELATIONS:
            raise ValueError(f"relation must be one of: {sorted(VALID_RELATIONS)}")
        return v


class AttendeeResponse(BaseModel):
    id: int
    type: str
    member_id: Optional[int]
    name: Optional[str]
    relation: Optional[str]
    dietary_restrictions: Optional[List[str]]
    model_config = ConfigDict(from_attributes=True)


# ----------------------------
# Mixins
# ----------------------------
class WithID(BaseModel):
    id: int


class WithTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime


# ----------------------------
# Inputs
# ----------------------------
class CreateBooking(BaseModel):
    user_id: int
    date: date
    service_period: str

    # Empty means draft (no tables yet)
    table_ids: List[int] = []
    attendees: List[AttendeeInput] = []

    ordering_mode: Optional[str] = None
    duration_minutes: int = 120
    notes: Optional[str] = None

    @field_validator("service_period")
    @classmethod
    def validate_service_period(cls, v: str) -> str:
        if v not in SERVICE_PERIODS:
            raise ValueError(f"service_period must be one of: {list(SERVICE_PERIODS.keys())}")
        return v

    @field_validator("ordering_mode")
    @classmethod
    def validate_ordering_mode(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_ORDERING_MODES:
            raise ValueError(f"ordering_mode must be one of: {sorted(VALID_ORDERING_MODES)}")
        return v


class UpdateBooking(BaseModel):
    date: Optional[date] = None
    service_period: Optional[str] = None
    table_ids: Optional[List[int]] = None
    attendees: Optional[List[AttendeeInput]] = None

    ordering_mode: Optional[str] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {sorted(VALID_STATUSES)}")
        return v

    @field_validator("service_period")
    @classmethod
    def validate_service_period(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in SERVICE_PERIODS:
            raise ValueError(f"service_period must be one of: {list(SERVICE_PERIODS.keys())}")
        return v

    @field_validator("ordering_mode")
    @classmethod
    def validate_ordering_mode(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_ORDERING_MODES:
            raise ValueError(f"ordering_mode must be one of: {sorted(VALID_ORDERING_MODES)}")
        return v


class GuestJoinBooking(BaseModel):
    """Public endpoint — guest joins via invite link"""
    name: str
    relation: str = "guest"
    dietary_restrictions: Optional[List[str]] = None


# ----------------------------
# Outputs
# ----------------------------
class BookingTableResponse(BaseModel):
    table_id: int
    model_config = ConfigDict(from_attributes=True)


class BookingResponse(WithID, WithTimestamps):
    user_id: int
    date: date
    service_period: str

    party_size: int = 0  # computed in build_response()
    status: str

    ordering_mode: Optional[str]
    invite_token: Optional[str]

    seated_at: Optional[datetime]
    duration_minutes: int
    notes: Optional[str]

    tables: List[BookingTableResponse] = []
    attendees: List[AttendeeResponse] = []

    # computed flags for frontend
    has_orders: bool = False  # to be wired later

    model_config = ConfigDict(from_attributes=True)