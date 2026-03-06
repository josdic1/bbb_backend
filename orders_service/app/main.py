# orders_service/app/main.py
import json

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from .database import Base, engine, get_db
from .models import Order, OrderItem, MenuItem
from .schema import (
    CreateMenuItem, UpdateMenuItem, MenuItemResponse,
    CreateOrder, UpdateOrder, OrderResponse,
    CreateOrderItem, OrderItemResponse,
)
from . import auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Orders Service", version="1.0.0")

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
# Helpers
# ---------------------------------------------------------------------------

def get_menu_item_or_404(item_id: int, db: Session) -> MenuItem:
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Menu item {item_id} not found")
    return item


def build_order_response(order: Order, db: Session) -> OrderResponse:
    """
    Populate menu_item on each OrderItem at read time.
    No cross-service FK — we resolve by ID against the local menu_items table.
    """
    item_responses = []
    for oi in order.items:
        menu_item_obj = db.query(MenuItem).filter(MenuItem.id == oi.menu_item_id).first()
        menu_item_resp = MenuItemResponse.model_validate(menu_item_obj) if menu_item_obj else None
        item_responses.append(OrderItemResponse(
            id=oi.id,
            order_id=oi.order_id,
            menu_item_id=oi.menu_item_id,
            quantity=oi.quantity,
            notes=oi.notes,
            price_at_time=oi.price_at_time,
            menu_item=menu_item_resp,
        ))

    return OrderResponse(
        id=order.id,
        booking_id=order.booking_id,
        attendee_id=order.attendee_id,
        status=order.status,
        notes=order.notes,
        is_active=order.is_active,
        items=item_responses,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


# ---------------------------------------------------------------------------
# Menu routes
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
    return get_menu_item_or_404(item_id, db)


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
    item = get_menu_item_or_404(item_id, db)
    updates = payload.model_dump(exclude_unset=True)
    if "dietary_restrictions" in updates:
        updates["dietary_restrictions"] = json.dumps(updates["dietary_restrictions"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/menu/{item_id}", status_code=204)
def deactivate_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_admin),
):
    item = get_menu_item_or_404(item_id, db)
    item.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Order routes
# ---------------------------------------------------------------------------

@app.post("/orders/", response_model=OrderResponse, status_code=201)
def create_order(
    payload: CreateOrder,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    # Validate all menu items exist and are active before writing anything
    resolved_items = []
    for ci in payload.items:
        menu_item = get_menu_item_or_404(ci.menu_item_id, db)
        if not menu_item.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Menu item {ci.menu_item_id} is not currently available",
            )
        resolved_items.append((ci, menu_item))

    order = Order(
        booking_id=payload.booking_id,
        attendee_id=payload.attendee_id,
        notes=payload.notes,
        status="pending",
    )
    db.add(order)
    db.flush()  # get order.id before adding items

    for ci, menu_item in resolved_items:
        db.add(OrderItem(
            order_id=order.id,
            menu_item_id=ci.menu_item_id,
            quantity=ci.quantity,
            notes=ci.notes,
            price_at_time=menu_item.price_cents,  # snapshot price now
        ))

    db.commit()
    db.refresh(order)
    return build_order_response(order, db)


@app.get("/orders/", response_model=List[OrderResponse])
def list_orders(
    booking_id: Optional[int] = Query(default=None),
    attendee_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    q = db.query(Order).filter(Order.is_active == True)
    if booking_id is not None:
        q = q.filter(Order.booking_id == booking_id)
    if attendee_id is not None:
        q = q.filter(Order.attendee_id == attendee_id)
    orders = q.order_by(Order.created_at).all()
    return [build_order_response(o, db) for o in orders]


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return build_order_response(order, db)


@app.patch("/orders/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    payload: UpdateOrder,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_staff_or_admin),
):
    order = db.query(Order).filter(Order.id == order_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(order, field, value)

    db.commit()
    db.refresh(order)
    return build_order_response(order, db)


# ---------------------------------------------------------------------------
# Order item routes
# ---------------------------------------------------------------------------

@app.post("/orders/{order_id}/items", response_model=OrderResponse, status_code=201)
def add_order_item(
    order_id: int,
    payload: CreateOrderItem,
    db: Session = Depends(get_db),
    current_user=Depends(auth.get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    menu_item = get_menu_item_or_404(payload.menu_item_id, db)
    if not menu_item.is_active:
        raise HTTPException(status_code=400, detail="Menu item is not currently available")

    db.add(OrderItem(
        order_id=order.id,
        menu_item_id=payload.menu_item_id,
        quantity=payload.quantity,
        notes=payload.notes,
        price_at_time=menu_item.price_cents,
    ))
    db.commit()
    db.refresh(order)
    return build_order_response(order, db)


@app.delete("/orders/{order_id}/items/{item_id}", response_model=OrderResponse)
def remove_order_item(
    order_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_staff_or_admin),
):
    order = db.query(Order).filter(Order.id == order_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    oi = db.query(OrderItem).filter(
        OrderItem.id == item_id,
        OrderItem.order_id == order_id,
    ).first()
    if not oi:
        raise HTTPException(status_code=404, detail="Order item not found")

    db.delete(oi)
    db.commit()
    db.refresh(order)
    return build_order_response(order, db)


@app.delete("/orders/{order_id}", status_code=204)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(auth.require_staff_or_admin),
):
    order = db.query(Order).filter(Order.id == order_id, Order.is_active == True).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.is_active = False
    db.commit()