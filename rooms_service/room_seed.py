"""
Abeyton Lodge - Room & Table Seed Script
Run with: poetry run python seed.py
Safe to re-run: skips rooms that already exist by name.
"""

from app.database import engine, SessionLocal
from app import models

models.Base.metadata.create_all(bind=engine)

ROOMS = [
    {
        "name": "Breakfast Nook",
        "is_active": True,
        "tables": [
            {"seats": 6},
        ]
    },
    {
        "name": "Card Room",
        "is_active": True,
        "tables": [
            {"seats": 10},
        ]
    },
    {
        "name": "Croquet Court",
        "is_active": True,
        "tables": [
            {"seats": 6},
            {"seats": 6},
            {"seats": 6},
        ]
    },
    {
        "name": "Living Room",
        "is_active": True,
        "tables": [
            {"seats": 6},
            {"seats": 6},
            {"seats": 6},
        ]
    },
    {
        "name": "Pool",
        "is_active": True,
        "tables": [
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
            {"seats": 4},
        ]
    },
]

def seed():
    db = SessionLocal()
    try:
        seeded = 0
        skipped = 0
        for room_data in ROOMS:
            exists = db.query(models.Room).filter(
                models.Room.name == room_data["name"]
            ).first()

            if exists:
                print(f"  SKIP  {room_data['name']} (already exists)")
                skipped += 1
                continue

            room = models.Room(
                name=room_data["name"],
                is_active=room_data["is_active"]
            )
            db.add(room)
            db.flush()  # get room.id without committing

            for t in room_data["tables"]:
                table = models.Table(seats=t["seats"], room_id=room.id)
                db.add(table)

            db.commit()
            print(f"  SEEDED {room_data['name']} ({len(room_data['tables'])} tables)")
            seeded += 1

        print(f"\nDone. {seeded} seeded, {skipped} skipped.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()