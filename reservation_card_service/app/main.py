# reservation_card_service/app/main.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import text

from . import models, database, auth

models.Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Reservation Card Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "null",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# Schemas
# ----------------------------

class ReservationCardResponse(BaseModel):
    id: int
    booking_id: int
    status: str
    booking_date: str
    service_period: str
    duration_minutes: int
    notes: Optional[str]
    booking_superstring: str
    creator_user_id: int
    creator_name: str
    creator_role: str
    party_size: int
    attendee_superstring: Optional[str]
    order_total_cents: int
    has_orders: bool
    flags: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    model_config = ConfigDict(from_attributes=True)


class UpsertCardRequest(BaseModel):
    booking_id: int
    actor_user_id: int
    actor_role: str


# ----------------------------
# DB query helpers
# ----------------------------

def fetch_booking(db: Session, booking_id: int):
    row = db.execute(
        text("""
            SELECT
                b.id,
                b.user_id,
                b.date,
                b.service_period,
                b.status,
                b.duration_minutes,
                b.notes,
                b.created_at
            FROM bookings b
            WHERE b.id = :booking_id
        """),
        {"booking_id": booking_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    return row._mapping


def fetch_creator(db: Session, user_id: int):
    row = db.execute(
        text("""
            SELECT
                u.id,
                u.role,
                COALESCE(m.name, u.email) AS display_name
            FROM users u
            LEFT JOIN members m ON m.user_id = u.id
            WHERE u.id = :user_id
            LIMIT 1
        """),
        {"user_id": user_id}
    ).fetchone()
    if not row:
        return {"id": user_id, "role": "unknown", "display_name": f"user_{user_id}"}
    return row._mapping


def fetch_room_name(db: Session, booking_id: int) -> str:
    row = db.execute(
        text("""
            SELECT COALESCE(r.name, 'Unknown Room') AS room_name
            FROM booking_tables bt
            JOIN tables t ON t.id = bt.table_id
            JOIN rooms r ON r.id = t.room_id
            WHERE bt.booking_id = :booking_id
            LIMIT 1
        """),
        {"booking_id": booking_id}
    ).fetchone()
    if not row:
        return "Unknown Room"
    return row._mapping["room_name"]


def fetch_attendees(db: Session, booking_id: int) -> list:
    rows = db.execute(
        text("""
            SELECT
                ba.id AS attendee_id,
                ba.type,
                ba.member_id,
                ba.name AS guest_name,
                COALESCE(m.name, ba.name, 'Unknown') AS display_name,
                ba.dietary_restrictions
            FROM booking_attendees ba
            LEFT JOIN members m ON m.id = ba.member_id
            WHERE ba.booking_id = :booking_id
            ORDER BY ba.id
        """),
        {"booking_id": booking_id}
    ).fetchall()
    return [r._mapping for r in rows]


def fetch_orders(db: Session, booking_id: int) -> list:
    rows = db.execute(
        text("""
            SELECT
                o.id AS order_id,
                o.attendee_id,
                o.status,
                COALESCE(SUM(oi.price_at_time * oi.quantity), 0) AS total_cents
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.booking_id = :booking_id AND o.is_active = true
            GROUP BY o.id, o.attendee_id, o.status
        """),
        {"booking_id": booking_id}
    ).fetchall()
    return [r._mapping for r in rows]


def fetch_seats(db: Session, booking_id: int) -> list:
    rows = db.execute(
        text("""
            SELECT attendee_id, table_id, seat_number
            FROM seat_assignments
            WHERE booking_id = :booking_id
        """),
        {"booking_id": booking_id}
    ).fetchall()
    return [r._mapping for r in rows]


# ----------------------------
# Card builder
# ----------------------------

def build_card_data(db: Session, booking_id: int, actor_user_id: int, actor_role: str) -> dict:
    booking = fetch_booking(db, booking_id)
    creator = fetch_creator(db, booking["user_id"])
    room_name = fetch_room_name(db, booking_id)
    attendees = fetch_attendees(db, booking_id)
    orders = fetch_orders(db, booking_id)
    seats = fetch_seats(db, booking_id)
    booking_tables = db.execute(
        text("SELECT table_id FROM booking_tables WHERE booking_id = :bid"),
        {"bid": booking_id}
    ).fetchall()
    table_str = "_".join([f"table{r[0]}" for r in booking_tables]) or "notable"
    booking_superstring = f"{booking['date']}_{booking['service_period']}_{room_name}_{table_str}"


    # Order lookup by attendee
    orders_by_attendee = {}
    for o in orders:
        aid = o["attendee_id"]
        if aid not in orders_by_attendee:
            orders_by_attendee[aid] = []
        orders_by_attendee[aid].append(o)

    # Seat lookup by attendee
    seats_by_attendee = {s["attendee_id"]: s for s in seats}

    # ATTENDEE_SUPERSTRING
    # Format: attendee_id: type_name_order#id OR NOORDERS_tableX_seatY
    attendee_lines = []
    has_dietary = False
    fully_seated = len(attendees) > 0

    for a in attendees:
        aid = a["attendee_id"]
        atype = a["type"]
        aname = a["display_name"].replace(" ", "")

        # Orders
        attendee_orders = orders_by_attendee.get(aid, [])
        if attendee_orders:
            order_str = "_".join([f"order#{o['order_id']}" for o in attendee_orders])
        else:
            order_str = "NOORDERS"

        # Seat
        seat = seats_by_attendee.get(aid)
        if seat:
            seat_str = f"table{seat['table_id']}_seat{seat['seat_number']}"
        else:
            seat_str = "UNSEATED"
            fully_seated = False

        attendee_lines.append(f"  {aid}: {atype}_{aname}_{order_str}_{seat_str}")

        if a["dietary_restrictions"]:
            has_dietary = True

    attendee_superstring = "\n".join(attendee_lines) if attendee_lines else None

    # Financials
    order_total_cents = sum(o["total_cents"] for o in orders)
    has_orders = len(orders) > 0

    # FLAGS
    flag_parts = []
    if has_orders:
        flag_parts.append("HAS_ORDERS")
    if fully_seated and len(attendees) > 0:
        flag_parts.append("FULLY_SEATED")
    if has_dietary:
        flag_parts.append("DIETARY_RESTRICTIONS")
    flags = " · ".join(flag_parts) if flag_parts else None

    # Actor string
    actor_display = fetch_creator(db, actor_user_id)
    actor_str = f"{actor_role}_{actor_display['display_name'].replace(' ', '')}"

    # Creator string
    creator_str = f"{creator['role']}_{creator['display_name'].replace(' ', '')}"

    return {
        "booking_id": booking_id,
        "status": booking["status"],
        "booking_date": str(booking["date"]),
        "service_period": booking["service_period"],
        "duration_minutes": booking["duration_minutes"],
        "notes": booking["notes"],
        "booking_superstring": booking_superstring,
        "creator_user_id": booking["user_id"],
        "creator_name": creator["display_name"],
        "creator_role": creator["role"],
        "party_size": len(attendees),
        "attendee_superstring": attendee_superstring,
        "order_total_cents": order_total_cents,
        "has_orders": has_orders,
        "flags": flags,
        "created_by": creator_str,
        "updated_by": actor_str,
    }


# ----------------------------
# Routes
# ----------------------------

@app.post("/cards/", response_model=ReservationCardResponse)
def upsert_card(
    req: UpsertCardRequest,
    db: Session = Depends(database.get_db),
):
    """
    Called by bookings_service (fire-and-forget) after any booking change.
    No auth required — internal only. Creates or fully rebuilds the card.
    """
    card_data = build_card_data(db, req.booking_id, req.actor_user_id, req.actor_role)

    existing = db.query(models.ReservationCard).filter(
        models.ReservationCard.booking_id == req.booking_id
    ).first()

    if existing:
        for key, value in card_data.items():
            setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        card = models.ReservationCard(**card_data)
        db.add(card)
        db.commit()
        db.refresh(card)
        return card


@app.get("/cards/", response_model=List[ReservationCardResponse])
def get_all_cards(
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    return db.query(models.ReservationCard).order_by(models.ReservationCard.booking_id).all()


@app.get("/cards/{booking_id}", response_model=ReservationCardResponse)
def get_card(
    booking_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    card = db.query(models.ReservationCard).filter(
        models.ReservationCard.booking_id == booking_id
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found — try POST /cards/ to generate it")
    return card


@app.delete("/cards/{booking_id}")
def delete_card(
    booking_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    card = db.query(models.ReservationCard).filter(
        models.ReservationCard.booking_id == booking_id
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
    return {"message": f"Card for booking {booking_id} deleted."}