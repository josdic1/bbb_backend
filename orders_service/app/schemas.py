# orders_service/app/schemas.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# MenuItem — read-only stub for embedding in order item responses.
# menu_service owns the full MenuItem API. This is just enough to display
# name/price alongside an order item without a cross-service HTTP call.
# Populated at read time by querying menu_items directly from the shared DB.
# ---------------------------------------------------------------------------

class MenuItemStub(BaseModel):
    id: int
    name: str
    category: str
    price_cents: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# OrderItem schemas
# ---------------------------------------------------------------------------

class CreateOrderItem(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1)
    notes: Optional[str] = None


class UpdateOrderItem(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = None


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    menu_item_id: int
    quantity: int
    notes: Optional[str] = None
    price_at_time: int
    # Populated at read time — None only if menu item was hard-deleted.
    menu_item: Optional[MenuItemStub] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Order schemas
# ---------------------------------------------------------------------------

class CreateOrder(BaseModel):
    booking_id: int
    attendee_id: Optional[int] = None
    notes: Optional[str] = None
    items: List[CreateOrderItem] = Field(default_factory=list)


class UpdateOrder(BaseModel):
    # Status flow: pending -> confirmed -> served
    status: Optional[str] = None
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    booking_id: int
    attendee_id: Optional[int] = None
    status: str
    notes: Optional[str] = None
    is_active: bool
    items: List[OrderItemResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)