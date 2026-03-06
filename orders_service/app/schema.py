import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# MenuItem schemas
# Defined locally — no import from menu_service. orders_service owns
# the menu_items table and resolves item data internally.
# ---------------------------------------------------------------------------

def _parse_dietary(value: str | List[str]) -> List[str]:
    """Accept either a JSON string from the DB or an already-decoded list."""
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


class MenuItemResponse(BaseModel):
    id: int
    name: str
    description: str
    price_cents: int
    category: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def decode_dietary(cls, data):
        if hasattr(data, "__dict__"):
            raw = getattr(data, "dietary_restrictions", "[]")
            data.__dict__["dietary_restrictions"] = _parse_dietary(raw)
        elif isinstance(data, dict):
            raw = data.get("dietary_restrictions", "[]")
            data["dietary_restrictions"] = _parse_dietary(raw)
        return data


class CreateMenuItem(BaseModel):
    name: str
    description: str
    price_cents: int
    category: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    is_active: bool = True


class UpdateMenuItem(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    category: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None
    is_active: Optional[bool] = None


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
    # Price captured at order creation — not re-fetched from menu item.
    price_at_time: int
    # Populated at read time by the route handler after querying MenuItem.
    # None if the menu item has been hard-deleted (shouldn't happen — use is_active).
    menu_item: Optional[MenuItemResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Order schemas
# ---------------------------------------------------------------------------

class CreateOrder(BaseModel):
    booking_id: int
    # attendee_id is optional — omit for a whole-booking order,
    # set for per-person ordering.
    attendee_id: Optional[int] = None
    notes: Optional[str] = None
    items: List[CreateOrderItem] = Field(default_factory=list)


class UpdateOrder(BaseModel):
    # Status transitions: pending -> confirmed -> served
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