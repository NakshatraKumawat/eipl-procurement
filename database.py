import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# If running on Render, it uses the Supabase PostgreSQL string. 
# Otherwise, it falls back to your local offline SQLite file!
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")

if DATABASE_URL.startswith("postgresql://"):
    # Fixes a common SQLAlchemy compatibility quirk with newer cloud strings
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()