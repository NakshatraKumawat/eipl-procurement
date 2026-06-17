import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# If running on Render, it uses the Supabase PostgreSQL string. 
# Otherwise, it falls back to your local offline SQLite file!
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")

if DATABASE_URL.startswith("postgresql"):
    # Handle both postgresql:// and postgresql+psycopg2:// formats
    if not DATABASE_URL.startswith("postgresql+psycopg2://"):
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


def run_migrations():
    """
    Safe, idempotent schema migrations using ALTER TABLE ... ADD COLUMN IF NOT EXISTS.
    Only runs on PostgreSQL (Render/Supabase). SQLite uses create_all and handles
    schema differences differently.

    Add new columns here whenever models.py is extended — never drop or rename columns
    through this function to avoid data loss.
    """
    if not DATABASE_URL.startswith("postgresql"):
        return  # SQLite: create_all() in app.py already handles it

    migrations = [
        # --- procurement_requests ---
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS is_new_item BOOLEAN DEFAULT FALSE",
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS new_item_name VARCHAR",
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS detailed_specification VARCHAR",
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS vendor VARCHAR",
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS unit_price FLOAT",
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS uom VARCHAR DEFAULT 'Nos'",
        "ALTER TABLE procurement_requests ADD COLUMN IF NOT EXISTS category VARCHAR",

        # --- material_assignments ---
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS custodian VARCHAR DEFAULT 'Common'",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS mis_filename VARCHAR",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS mis_filedata BYTEA",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS mis_uploaded_by_id INTEGER REFERENCES users(id)",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS mis_upload_timestamp TIMESTAMP",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS is_return BOOLEAN DEFAULT FALSE",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS return_filename VARCHAR",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS return_filedata BYTEA",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS asset_unit_id INTEGER REFERENCES asset_units(id)",
        "ALTER TABLE material_assignments ADD COLUMN IF NOT EXISTS department VARCHAR DEFAULT 'General Operations'",

        # --- grn_records ---
        "ALTER TABLE grn_records ADD COLUMN IF NOT EXISTS vendor VARCHAR",
        "ALTER TABLE grn_records ADD COLUMN IF NOT EXISTS unit_price FLOAT",
        "ALTER TABLE grn_records ADD COLUMN IF NOT EXISTS grn_no VARCHAR",
        "ALTER TABLE grn_records ADD COLUMN IF NOT EXISTS challan_no VARCHAR",
        "ALTER TABLE grn_records ADD COLUMN IF NOT EXISTS grn_filedata BYTEA",
        "ALTER TABLE grn_records ADD COLUMN IF NOT EXISTS uom VARCHAR DEFAULT 'Nos'",

        # --- items ---
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS uom VARCHAR",
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS storage_site VARCHAR DEFAULT 'Store Yard'",
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS minimum_stock INTEGER DEFAULT 0",

        # --- users ---
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR DEFAULT 'EIPL Officer'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS designation VARCHAR DEFAULT 'Operations Specialist'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS workstation_location VARCHAR DEFAULT 'Corporate HQ'",

        # --- asset_units ---
        "ALTER TABLE asset_units ADD COLUMN IF NOT EXISTS current_assignment_id INTEGER REFERENCES material_assignments(id)",
        "ALTER TABLE asset_units ADD COLUMN IF NOT EXISTS retired_at TIMESTAMP",
        "ALTER TABLE asset_units ADD COLUMN IF NOT EXISTS notes VARCHAR",

        # --- material_requests ---
        "ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS is_new_item BOOLEAN DEFAULT FALSE",
        "ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS new_item_name VARCHAR",
        "ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS detailed_specification VARCHAR",
        "ALTER TABLE material_requests ADD COLUMN IF NOT EXISTS total_estimated_cost FLOAT DEFAULT 0.0",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
            except Exception as e:
                # Log but don't crash — column may already exist or table not yet created
                print(f"[migration warning] {e}")
        conn.commit()


# Run migrations automatically on import (i.e. on every app startup)
run_migrations()