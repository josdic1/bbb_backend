"""
Abeyton Lodge - Admin User Seed Script
Run with: poetry run python admin_seed.py
Creates the first admin user. Safe to re-run — skips if email already exists.
"""

from app.database import SessionLocal, engine
from app import models
from app.auth import hash_password

models.Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.email == "josh@demo.com").first()
        if existing:
            print("SKIP — josh@demo.com already exists")
            return

        admin = models.User(
            email="josh@demo.com",
            hashed_password=hash_password("111111"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"SEEDED admin user: josh@demo.com (id={admin.id})")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()