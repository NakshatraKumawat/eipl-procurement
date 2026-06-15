"""
patch_material_assignments_pg.py
---------------------------------
Run this ONCE against your Supabase/Postgres database to add the
missing columns on material_assignments that exist in models.py
but not yet in the live DB:

    - mis_filedata      (BYTEA / LargeBinary)
    - is_return         (BOOLEAN)
    - return_filename   (TEXT)
    - return_filedata   (BYTEA / LargeBinary)

Safe to re-run: each ALTER uses IF NOT EXISTS, so already-applied
columns are skipped automatically.

Works for both Postgres (production) and SQLite (local), since
SQLite (3.x) also supports "ADD COLUMN IF NOT EXISTS"... actually
SQLite does NOT support IF NOT EXISTS on ALTER, so this script
detects the dialect and branches accordingly.

Usage:
    python patch_material_assignments_pg.py
"""

from database import engine
from sqlalchemy import text, inspect


COLUMNS_TO_ADD = [
    ("mis_filedata", "BYTEA"),
    ("is_return", "BOOLEAN DEFAULT FALSE"),
    ("return_filename", "TEXT"),
    ("return_filedata", "BYTEA"),
]

# SQLite type equivalents (SQLite is loosely typed, BLOB works for bytes)
SQLITE_TYPES = {
    "BYTEA": "BLOB",
    "BOOLEAN DEFAULT FALSE": "BOOLEAN DEFAULT 0",
}


def patch():
    dialect = engine.dialect.name
    print(f"Detected database dialect: {dialect}")

    inspector = inspect(engine)
    existing_columns = [col["name"] for col in inspector.get_columns("material_assignments")]
    print(f"Existing columns: {existing_columns}")

    with engine.connect() as conn:
        for col_name, pg_type in COLUMNS_TO_ADD:
            if col_name in existing_columns:
                print(f"  -> '{col_name}' already exists. Skipping.")
                continue

            if dialect == "sqlite":
                col_type = SQLITE_TYPES.get(pg_type, pg_type)
                stmt = f"ALTER TABLE material_assignments ADD COLUMN {col_name} {col_type};"
            else:
                # Postgres supports IF NOT EXISTS on ADD COLUMN (9.6+)
                stmt = (
                    f"ALTER TABLE material_assignments "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {pg_type};"
                )

            print(f"  -> Running: {stmt}")
            conn.execute(text(stmt))
            print(f"  -> Added '{col_name}' successfully.")

        conn.commit()

    print("\nPatch complete! Restart your application.")


if __name__ == "__main__":
    patch()
