# menu_service/app/schemas.py
import json
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
        """
        SQLAlchemy gives us the raw Text column value (a JSON string).
        Convert it to a list before Pydantic validates the field.
        """
        if hasattr(data, "__dict__"):
            # ORM object — work on a plain dict copy
            raw = getattr(data, "dietary_restrictions", "[]")
            data.__dict__["dietary_restrictions"] = _parse_dietary(raw)
        elif isinstance(data, dict):
            raw = data.get("dietary_restrictions", "[]")
            data["dietary_restrictions"] = _parse_dietary(raw)
        return data