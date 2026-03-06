# users_service/app/main.py
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import models, schemas, database, auth

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="...")

# Dev-only CORS:
# - If you run a dev server (React/Vite), allow that origin (usually :5173)
# - If you open index.html via file://, the Origin is "null"
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

# ----------------------------
# Auth
# ----------------------------
@app.post("/auth/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    token = auth.create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UserResponse)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ----------------------------
# Users
# ----------------------------
@app.post("/users/", response_model=schemas.UserResponse)
def create_user(
    user: schemas.CreateUser,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(auth.require_admin),
):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = models.User(
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        member_number=user.member_number,
        role=user.role,
    )
    db.add(db_user)
    db.flush()

    for m in user.members:
        db.add(
            models.Member(
                user_id=db_user.id,
                name=m.name,
                relation=m.relation,
                dietary_restrictions=m.dietary_restrictions or [],
            )
        )

    db.commit()
    db.refresh(db_user)
    return db_user


@app.get("/users/", response_model=List[schemas.UserResponse])
def get_users(
    db: Session = Depends(database.get_db),
    _: models.User = Depends(auth.require_staff_or_admin),
):
    return db.query(models.User).all()


@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role == "member" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return db_user


@app.patch("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int,
    user: schemas.UpdateUser,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role == "member" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    for key, value in user.model_dump(exclude_unset=True).items():
        setattr(db_user, key, value)

    db.commit()
    db.refresh(db_user)
    return db_user


@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(auth.require_admin),
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(db_user)
    db.commit()
    return {"message": f"User {user_id} deleted."}


# ----------------------------
# Members
# ----------------------------
@app.get("/members/", response_model=List[schemas.MemberResponse])
def get_all_members(
    db: Session = Depends(database.get_db),
    _: models.User = Depends(auth.require_staff_or_admin),
):
    return db.query(models.Member).all()


@app.get("/users/{user_id}/members/", response_model=List[schemas.MemberResponse])
def get_members_for_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role == "member" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(models.Member).filter(models.Member.user_id == user_id).all()


@app.post("/members/", response_model=schemas.MemberResponse)
def create_member(
    member: schemas.CreateMember,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_member = models.Member(
        user_id=current_user.id,
        name=member.name,
        relation=member.relation,
        dietary_restrictions=member.dietary_restrictions or [],
    )
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member


@app.patch("/members/{member_id}", response_model=schemas.MemberResponse)
def update_member(
    member_id: int,
    member: schemas.UpdateMember,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")

    if current_user.role == "member" and db_member.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for key, value in member.model_dump(exclude_unset=True).items():
        setattr(db_member, key, value)

    db.commit()
    db.refresh(db_member)
    return db_member


@app.delete("/members/{member_id}")
def delete_member(
    member_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")

    if current_user.role == "member" and db_member.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(db_member)
    db.commit()
    return {"message": f"Member {member_id} removed."}