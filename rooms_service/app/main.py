# rooms_service/app/main.py
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, database, auth

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="...")

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

# GET /rooms/ — no auth (needed by booking flow and dev console)
@app.get("/rooms/", response_model=List[schemas.RoomResponse])
def get_rooms(db: Session = Depends(database.get_db)):
    return db.query(models.Room).all()


# POST /rooms/ — admin only
@app.post("/rooms/", response_model=schemas.RoomResponse)
def create_room(
    room: schemas.CreateRoom,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_admin),
):
    db_room = models.Room(name=room.name, is_active=room.is_active)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)

    for table_data in room.tables:
        db.add(models.Table(seats=table_data.seats, room_id=db_room.id))

    db.commit()
    db.refresh(db_room)
    return db_room


# PATCH /rooms/{room_id} — admin only
@app.patch("/rooms/{room_id}", response_model=schemas.RoomResponse)
def update_room(
    room_id: int,
    room: schemas.UpdateRoom,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_admin),
):
    db_room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    for key, value in room.model_dump(exclude_unset=True).items():
        setattr(db_room, key, value)

    db.commit()
    db.refresh(db_room)
    return db_room


# DELETE /rooms/{room_id} — admin only
@app.delete("/rooms/{room_id}")
def delete_room(
    room_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_admin),
):
    db_room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    db.delete(db_room)
    db.commit()
    return {"message": f"Room {room_id} and its tables dissolved."}


# POST /rooms/{room_id}/tables/ — admin only
@app.post("/rooms/{room_id}/tables/", response_model=schemas.TableResponse)
def add_table(
    room_id: int,
    table: schemas.TableAtom,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_admin),
):
    db_room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    new_table = models.Table(seats=table.seats, room_id=room_id)
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    return new_table


# PATCH /tables/{table_id} — admin only
@app.patch("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(
    table_id: int,
    table: schemas.TableAtom,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_admin),
):
    db_table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")

    db_table.seats = table.seats
    db.commit()
    db.refresh(db_table)
    return db_table


# DELETE /tables/{table_id} — admin only
@app.delete("/tables/{table_id}")
def delete_table(
    table_id: int,
    db: Session = Depends(database.get_db),
    _: dict = Depends(auth.require_admin),
):
    db_table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")

    db.delete(db_table)
    db.commit()
    return {"message": f"Table {table_id} removed."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)