# root/shelly.py
from app.database import engine
from app.models import Base

def reset_database():
    print("Re-syncing database chemistry...")
    
    # 1. Dissolve existing tables
    Base.metadata.drop_all(bind=engine)
    print("Old tables dropped.")
    
    # 2. Forge new tables with the 'seats' column
    Base.metadata.create_all(bind=engine)
    print("New tables created with 'seats' column.")

if __name__ == "__main__":
    reset_database()