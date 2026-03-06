# rooms_service/app/schemas.py
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# ----------------------------
# Atoms (pure field sets)
# ----------------------------
class TableAtom(BaseModel):
    seats: int


class RoomAtom(BaseModel):
    name: str
    is_active: bool = True


# ----------------------------
# Mixins (reusable “add-ons”)
# ----------------------------
class WithID(BaseModel):
    id: int


class WithTables(BaseModel):
    tables: List[TableAtom] = []


# ----------------------------
# Inputs (client -> API)
# ----------------------------
class CreateRoom(RoomAtom, WithTables):
    pass


class UpdateRoom(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


# ----------------------------
# Outputs (API -> client)
# ----------------------------
class TableResponse(TableAtom, WithID):
    model_config = ConfigDict(from_attributes=True)


class RoomResponse(RoomAtom, WithID):
    tables: List[TableResponse] = []
    model_config = ConfigDict(from_attributes=True)