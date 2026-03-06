# reservation_card_service/app/models.py
from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ReservationCard(Base):
    __tablename__ = "reservation_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booking_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    # Top-level fields
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    booking_date: Mapped[str] = mapped_column(String(20), nullable=False)       # stored as ISO string
    service_period: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Computed superstrings
    booking_superstring: Mapped[str] = mapped_column(String(200), nullable=False)
    # e.g. "2026-03-15_dinner_Main Dining Room"

    # Creator
    creator_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    creator_name: Mapped[str] = mapped_column(String(120), nullable=False)
    creator_role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Party
    party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attendee_superstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # e.g. "12:member_JoshDicker_order#7_table8_seat2\n13:guest_JohnSmith_NOORDERS_table8_seat3"

    # Financials
    order_total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_orders: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Flags
    flags: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # e.g. "HAS_ORDERS · FULLY_SEATED · DIETARY_RESTRICTIONS"

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("TIMEZONE('utc', now())"),
        onupdate=text("TIMEZONE('utc', now())"),
    )
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    # e.g. "admin_JoshDicker"
    updated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    # e.g. "staff_MikeRoss"