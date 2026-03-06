import json

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from .database import Base, engine, get_db
from .models import MenuItem
from .schema import CreateMenuItem, UpdateMenuItem, MenuItemResponse
from . import auth

# ---------------------------------------------------------------------------
# Import seed data from constants
# ---------------------------------------------------------------------------
from .constants.menu_items import MENU_ITEMS

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Menu Service", version="1.0.0")

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

# ---------------------------------------------------------------------------
# Seed on startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def seed_menu():
    """Seed menu_items table from constants if empty."""
    db: Session = next(get_db())
    try:
        if db.query(MenuItem).count() == 0:
            for item in MENU_ITEMS.values():
                db.add(MenuItem(
                    name=item["name"],
                    description=item["description"],
                    category=item["category"],
                    price_cents=item["price_cents"],
                    dietary_restrictions=json.dumps(item.get("dietary_restrictions", [])),
                    is_active=item.get("is_active", True),
                ))
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/menu/", response_model=List[MenuItemResponse])
def list_menu_items(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    q = db.query(MenuItem)
    if active_only:
        q = q.filter(MenuItem.is_active == True)
    return q.order_by(MenuItem.category, MenuItem.name).all()


@app.get("/menu/{item_id}", response_model=MenuItemResponse)
def get_menu_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item


@app.post("/menu/", response_model=MenuItemResponse, status_code=201)
def create_menu_item(
    payload: CreateMenuItem,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_admin),
):
    item = MenuItem(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        price_cents=payload.price_cents,
        dietary_restrictions=json.dumps(payload.dietary_restrictions),
        is_active=payload.is_active,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/menu/{item_id}", response_model=MenuItemResponse)
def update_menu_item(
    item_id: int,
    payload: UpdateMenuItem,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_admin),
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    updates = payload.model_dump(exclude_unset=True)
    if "dietary_restrictions" in updates:
        updates["dietary_restrictions"] = json.dumps(updates["dietary_restrictions"])

    for field, value in updates.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@app.delete("/menu/{item_id}", status_code=204)
def delete_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_admin),
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    # Soft delete — preserve history
    item.is_active = False
    db.commit()