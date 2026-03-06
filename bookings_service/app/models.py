# bookings_service/app/models.py
from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Date,
    ForeignKey,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    service_period: Mapped[str] = mapped_column(String(20), nullable=False)  # lunch | dinner

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
    )  # draft | confirmed | seated | completed | cancelled

    # Ordering mode
    ordering_mode: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )  # group | inperson | None
    invite_token: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        unique=True,
        index=True,
    )  # UUID when ordering_mode=group

    # Timing
    seated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )

    tables: Mapped[List["BookingTable"]] = relationship(
        "BookingTable",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attendees: Mapped[List["BookingAttendee"]] = relationship(
        "BookingAttendee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class BookingTable(Base):
    __tablename__ = "booking_tables"

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    table_id: Mapped[int] = mapped_column(Integer, nullable=False, primary_key=True)


class BookingAttendee(Base):
    __tablename__ = "booking_attendees"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(String(10), nullable=False)  # member | guest
    member_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    relation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # primary | family | guest
    dietary_restrictions: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)