# bookings_service/app/main.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone, date
import uuid
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from . import models, schemas, database, auth
from .constants.service_periods import DINNER_DAYS

models.Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Bookings Service", lifespan=lifespan)

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
# Helpers
# ----------------------------

def check_availability(
    db: Session,
    table_ids: List[int],
    booking_date: date,
    service_period: str,
    exclude_booking_id: Optional[int] = None,
):
    if not table_ids:
        return

    query = (
        db.query(models.BookingTable)
        .join(models.Booking)
        .filter(
            models.Booking.date == booking_date,
            models.Booking.service_period == service_period,
            models.Booking.status.in_(["confirmed", "seated"]),
            models.BookingTable.table_id.in_(table_ids),
        )
    )

    if exclude_booking_id:
        query = query.filter(models.Booking.id != exclude_booking_id)

    conflicts = query.all()
    if conflicts:
        taken = [c.table_id for c in conflicts]
        raise HTTPException(
            status_code=409,
            detail=f"Tables already booked for this slot: {taken}",
        )


def validate_attendees(attendees: List[schemas.AttendeeInput]):
    for a in attendees:
        if a.type == "member" and not a.member_id:
            raise HTTPException(status_code=400, detail="member_id required for type=member")
        if a.type == "guest" and not a.name:
            raise HTTPException(status_code=400, detail="name required for type=guest")


def validate_member_ownership(db: Session, user_id: int, attendees: List[schemas.AttendeeInput]):
    member_attendees = [a for a in attendees if a.type == "member"]
    if not member_attendees:
        return

    result = db.execute(
        text("SELECT id FROM members WHERE user_id = :user_id"),
        {"user_id": user_id}
    ).fetchall()

    valid_member_ids = {row.id for row in result}

    for a in member_attendees:
        if a.member_id not in valid_member_ids:
            raise HTTPException(
                status_code=403,
                detail=f"Member {a.member_id} does not belong to this user"
            )


def add_attendees(db: Session, booking_id: int, attendees: List[schemas.AttendeeInput]):
    for a in attendees:
        db.add(
            models.BookingAttendee(
                booking_id=booking_id,
                type=a.type,
                member_id=a.member_id,
                name=a.name,
                relation=a.relation,
                dietary_restrictions=a.dietary_restrictions,
            )
        )


def build_response(db_booking: models.Booking, db: Session) -> schemas.BookingResponse:
    r = schemas.BookingResponse.model_validate(db_booking)
    r.party_size = len(db_booking.attendees)
    count = db.execute(
        text("SELECT COUNT(*) FROM orders WHERE booking_id=:bid AND is_active=true"),
        {"bid": db_booking.id}
    ).scalar()
    r.has_orders = (count or 0) > 0
    return r


# ----------------------------
# Bookings
# ----------------------------

@app.post("/bookings/", response_model=schemas.BookingResponse)
def create_booking(
    booking: schemas.CreateBooking,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user),
):
    if booking.service_period == "dinner" and booking.date.weekday() not in DINNER_DAYS:
        raise HTTPException(status_code=400, detail="Dinner is only available Thu-Sun")

    if booking.attendees:
        validate_attendees(booking.attendees)
        validate_member_ownership(db, current_user["id"], booking.attendees)

    invite_token = str(uuid.uuid4()) if booking.ordering_mode == "group" else None

    db_booking = models.Booking(
        user_id=booking.user_id,
        date=booking.date,
        service_period=booking.service_period,
        status="draft",
        ordering_mode=booking.ordering_mode,
        invite_token=invite_token,
        duration_minutes=booking.duration_minutes,
        notes=booking.notes,
    )
    db.add(db_booking)
    db.flush()

    for table_id in booking.table_ids:
        db.add(models.BookingTable(booking_id=db_booking.id, table_id=table_id))

    add_attendees(db, db_booking.id, booking.attendees)

    db.commit()
    db.refresh(db_booking)
    return build_response(db_booking, db)


@app.get("/bookings/", response_model=List[schemas.BookingResponse])
def get_bookings(
    booking_date: Optional[date] = None,
    service_period: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    query = db.query(models.Booking)
    if booking_date:
        query = query.filter(models.Booking.date == booking_date)
    if service_period:
        query = query.filter(models.Booking.service_period == service_period)
    if status:
        query = query.filter(models.Booking.status == status)
    return [build_response(b, db) for b in query.all()]


@app.get("/bookings/{booking_id}", response_model=schemas.BookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user),
):
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if current_user["role"] == "member" and db_booking.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return build_response(db_booking, db)


@app.patch("/bookings/{booking_id}", response_model=schemas.BookingResponse)
def update_booking(
    booking_id: int,
    booking: schemas.UpdateBooking,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user),
):
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if db_booking.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Only draft bookings can be edited (current status: {db_booking.status})"
        )

    if current_user["role"] == "member" and db_booking.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if booking.table_ids is not None or booking.date is not None or booking.service_period is not None:
        check_date = booking.date or db_booking.date
        check_period = booking.service_period or db_booking.service_period
        check_tables = booking.table_ids or [t.table_id for t in db_booking.tables]
        check_availability(db, check_tables, check_date, check_period, exclude_booking_id=booking_id)

    if booking.ordering_mode == "group" and not db_booking.invite_token:
        db_booking.invite_token = str(uuid.uuid4())
    elif booking.ordering_mode == "inperson":
        db_booking.invite_token = None

    for key, value in booking.model_dump(exclude_unset=True, exclude={"table_ids", "attendees"}).items():
        setattr(db_booking, key, value)

    if booking.table_ids is not None:
        db.query(models.BookingTable).filter(models.BookingTable.booking_id == booking_id).delete()
        for table_id in booking.table_ids:
            db.add(models.BookingTable(booking_id=booking_id, table_id=table_id))

    if booking.attendees is not None:
        validate_attendees(booking.attendees)
        validate_member_ownership(db, current_user["id"], booking.attendees)
        db.query(models.BookingAttendee).filter(models.BookingAttendee.booking_id == booking_id).delete()
        add_attendees(db, booking_id, booking.attendees)

    db.commit()
    db.refresh(db_booking)
    return build_response(db_booking, db)


@app.patch("/bookings/{booking_id}/confirm", response_model=schemas.BookingResponse)
def confirm_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    current_user: dict = Depends(auth.get_current_user),
):
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if current_user["role"] == "member" and db_booking.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if db_booking.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Only draft bookings can be confirmed (current status: {db_booking.status})"
        )

    missing = []
    if not db_booking.attendees:
        missing.append("at least one attendee required")
    if not db_booking.date:
        missing.append("date required")
    if not db_booking.service_period:
        missing.append("meal type required")

    table_ids = [t.table_id for t in db_booking.tables]
    if not table_ids:
        missing.append("at least one table required")

    if missing:
        raise HTTPException(
            status_code=400,
            detail={"reason": "booking incomplete", "missing": missing}
        )

    if db_booking.service_period == "dinner" and db_booking.date.weekday() not in DINNER_DAYS:
        raise HTTPException(status_code=400, detail="Dinner is only available Thu-Sun")

    check_availability(db, table_ids, db_booking.date, db_booking.service_period)

    db_booking.status = "confirmed"
    db.commit()
    db.refresh(db_booking)
    return build_response(db_booking, db)


@app.patch("/bookings/{booking_id}/seat", response_model=schemas.BookingResponse)
def seat_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.status != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed bookings can be seated")

    db_booking.status = "seated"
    db_booking.seated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_booking)
    return build_response(db_booking, db)


@app.patch("/bookings/{booking_id}/close", response_model=schemas.BookingResponse)
def close_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if db_booking.status != "seated":
        raise HTTPException(status_code=400, detail="Only seated bookings can be closed")

    db_booking.status = "completed"
    db.commit()
    db.refresh(db_booking)
    return build_response(db_booking, db)


@app.delete("/bookings/{booking_id}")
def cancel_booking(
    booking_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_staff_or_admin),
):
    db_booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if db_booking.status == "completed":
        raise HTTPException(status_code=400, detail="Completed bookings cannot be cancelled")

    db_booking.status = "cancelled"
    db.commit()
    return {"message": f"Booking {booking_id} cancelled."}


# ----------------------------
# Public invite link — no auth
# ----------------------------

@app.get("/bookings/join/{token}", response_model=schemas.BookingResponse)
def get_booking_by_token(token: str, db: Session = Depends(database.get_db)):
    db_booking = db.query(models.Booking).filter(models.Booking.invite_token == token).first()
    if not db_booking or db_booking.status in ("completed", "cancelled"):
        raise HTTPException(status_code=404, detail="Invite link not found or expired")
    return build_response(db_booking, db)


@app.post("/bookings/join/{token}", response_model=schemas.BookingResponse)
def join_booking_as_guest(token: str, guest: schemas.GuestJoinBooking, db: Session = Depends(database.get_db)):
    db_booking = db.query(models.Booking).filter(models.Booking.invite_token == token).first()
    if not db_booking or db_booking.status in ("completed", "cancelled"):
        raise HTTPException(status_code=404, detail="Invite link not found or expired")

    db.add(
        models.BookingAttendee(
            booking_id=db_booking.id,
            type="guest",
            name=guest.name,
            relation=guest.relation,
            dietary_restrictions=guest.dietary_restrictions,
        )
    )

    db.commit()
    db.refresh(db_booking)
    return build_response(db_booking, db)


# ----------------------------
# Availability — no auth
# ----------------------------

@app.get("/availability/")
def get_availability(booking_date: date, service_period: str, db: Session = Depends(database.get_db)):
    if service_period not in ("lunch", "dinner"):
        raise HTTPException(status_code=400, detail="Invalid service period")

    booked = (
        db.query(models.BookingTable)
        .join(models.Booking)
        .filter(
            models.Booking.date == booking_date,
            models.Booking.service_period == service_period,
            models.Booking.status.in_(["confirmed", "seated"]),
        )
        .all()
    )

    booked_table_ids = [b.table_id for b in booked]
    return {
        "date": booking_date,
        "service_period": service_period,
        "booked_table_ids": booked_table_ids,
    }