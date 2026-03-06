# rooms_service/app/main.py
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, database

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="...")

# Dev-only CORS:
# - If you run a dev server (React/Vite), allow that origin (usually :5173)
# - If you open index.html via file://, the Origin is "null"
# NOTE: You do NOT need to include the API's own origin/port here (8080/8082/etc).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Forge a Room (create room + tables)
@app.post("/rooms/", response_model=schemas.RoomResponse)
def create_room(room: schemas.CreateRoom, db: Session = Depends(database.get_db)):
    db_room = models.Room(name=room.name, is_active=room.is_active)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)

    for table_data in room.tables:
        db.add(models.Table(seats=table_data.seats, room_id=db_room.id))

    db.commit()
    db.refresh(db_room)
    return db_room


# 2. Get the Rolodex (all rooms + all tables)
@app.get("/rooms/", response_model=List[schemas.RoomResponse])
def get_rooms(db: Session = Depends(database.get_db)):
    return db.query(models.Room).all()


# 3. Update a Room
@app.patch("/rooms/{room_id}", response_model=schemas.RoomResponse)
def update_room(room_id: int, room: schemas.UpdateRoom, db: Session = Depends(database.get_db)):
    db_room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    update_data = room.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_room, key, value)

    db.commit()
    db.refresh(db_room)
    return db_room


# 4. Delete a Room
@app.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(database.get_db)):
    db_room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    db.delete(db_room)
    db.commit()
    return {"message": f"Room {room_id} and its tables dissolved."}


# Add a table to an existing room
@app.post("/rooms/{room_id}/tables/", response_model=schemas.TableResponse)
def add_table(room_id: int, table: schemas.TableAtom, db: Session = Depends(database.get_db)):
    db_room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not db_room:
        raise HTTPException(status_code=404, detail="Room not found")

    new_table = models.Table(seats=table.seats, room_id=room_id)
    db.add(new_table)
    db.commit()
    db.refresh(new_table)
    return new_table


# Update a table's seat count
@app.patch("/tables/{table_id}", response_model=schemas.TableResponse)
def update_table(table_id: int, table: schemas.TableAtom, db: Session = Depends(database.get_db)):
    db_table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")

    db_table.seats = table.seats
    db.commit()
    db.refresh(db_table)
    return db_table


# Delete a table
@app.delete("/tables/{table_id}")
def delete_table(table_id: int, db: Session = Depends(database.get_db)):
    db_table = db.query(models.Table).filter(models.Table.id == table_id).first()
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")

    db.delete(db_table)
    db.commit()
    return {"message": f"Table {table_id} removed."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)