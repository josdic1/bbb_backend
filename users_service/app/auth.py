import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session

from . import database, models

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash or not isinstance(stored_hash, str):
        return False

    try:
        return pwd_context.verify(plain_password, stored_hash)
    except (UnknownHashError, ValueError):
        return False


def verify_and_update_password(
    plain_password: str, stored_hash: Optional[str]
) -> tuple[bool, Optional[str]]:
    if not stored_hash or not isinstance(stored_hash, str):
        return False, None

    try:
        valid, new_hash = pwd_context.verify_and_update(plain_password, stored_hash)
        return valid, new_hash
    except (UnknownHashError, ValueError):
        return False, None


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception

    return user


def require_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    user_role = getattr(current_user, "role", None)
    is_admin = getattr(current_user, "is_admin", None)

    if user_role == "admin" or is_admin is True:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def require_staff_or_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    user_role = getattr(current_user, "role", None)
    is_admin = getattr(current_user, "is_admin", None)
    is_staff = getattr(current_user, "is_staff", None)

    if user_role in {"admin", "staff"} or is_admin is True or is_staff is True:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Staff or admin access required",
    )