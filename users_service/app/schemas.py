# users_service/app/schemas.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants.dietary import DIETARY_RESTRICTIONS

VALID_ROLES = {"member", "staff", "admin"}


# ----------------------------
# Atoms
# ----------------------------
class MemberAtom(BaseModel):
    name: str = Field(..., max_length=120)
    relation: Optional[str] = Field(None, max_length=50)
    dietary_restrictions: Optional[List[str]] = None

    @field_validator("dietary_restrictions")
    @classmethod
    def validate_dietary(cls, v: Optional[List[str]]):
        if v is None:
            return v
        invalid = [d for d in v if d not in DIETARY_RESTRICTIONS]
        if invalid:
            raise ValueError(f"Invalid dietary restrictions: {invalid}")
        return v


class UserAtom(BaseModel):
    email: str
    role: str = "member"
    member_number: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str):
        if v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {sorted(VALID_ROLES)}")
        return v


# ----------------------------
# Mixins
# ----------------------------
class WithID(BaseModel):
    id: int


class WithTimestamps(BaseModel):
    created_at: datetime


# ----------------------------
# Inputs
# ----------------------------
class CreateUser(UserAtom):
    password: str
    members: List[MemberAtom] = []


class UpdateUser(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    member_number: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]):
        if v and v not in VALID_ROLES:
            raise ValueError(f"Role must be one of: {sorted(VALID_ROLES)}")
        return v


class CreateMember(MemberAtom):
    pass


class UpdateMember(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    relation: Optional[str] = Field(None, max_length=50)
    dietary_restrictions: Optional[List[str]] = None
    is_active: Optional[bool] = None

    @field_validator("dietary_restrictions")
    @classmethod
    def validate_dietary(cls, v: Optional[List[str]]):
        if v is None:
            return v
        invalid = [d for d in v if d not in DIETARY_RESTRICTIONS]
        if invalid:
            raise ValueError(f"Invalid dietary restrictions: {invalid}")
        return v


# ----------------------------
# Outputs
# ----------------------------
class MemberResponse(MemberAtom, WithID, WithTimestamps):
    user_id: int
    is_active: bool
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserAtom, WithID, WithTimestamps):
    is_active: bool
    members: List[MemberResponse] = []
    model_config = ConfigDict(from_attributes=True)