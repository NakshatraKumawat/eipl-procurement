"""
patch_asset_unit_pg.py
-----------------------
Run this ONCE against your Supabase/Postgres database to add ALL
columns on material_assignments that exist in models.py but may be
missing from the live DB.

Specifically fixes:
    - asset_unit_id  (INTEGER, FK to asset_units.id)

Also ensures the asset_units table itself exists (needed for the FK).

Safe to re-run: existing columns are detected and skipped.

Usage:
    python patch_asset_unit_pg.py
"""

from database import engine
from sqlalchemy import text, inspect
import models  # ensures all model classes are registered


def patch():
    dialect = engine.dialect.name
    print(f"Detected database dialect: {dialect}")

    # Step 1 — ensure asset_units table exists (models.Base.metadata handles this)
    print("\nEnsuring asset_units table exists...")
    models.Base.metadata.create_all(bind=engine)
    print("  -> Tables verified / created.")

    # Step 2 — add missing columns to material_assignments
    inspector = inspect(engine)
    existing_columns = [col["name"] for col in inspector.get_columns("material_assignments")]
    print(f"\nExisting material_assignments columns: {existing_columns}")

    COLUMNS_TO_ADD = [
        # (column_name, postgres_type, sqlite_type)
        ("asset_unit_id", "INTEGER REFERENCES asset_units(id)", "INTEGER"),
        # Include others here if you ever need to re-run this on a fresh DB:
        ("mis_filedata",         "BYTEA",                  "BLOB"),
        ("is_return",            "BOOLEAN DEFAULT FALSE",  "BOOLEAN DEFAULT 0"),
        ("return_filename",      "TEXT",                   "TEXT"),
        ("return_filedata",      "BYTEA",                  "BLOB"),
        ("custodian",            "TEXT DEFAULT 'Common'",  "TEXT DEFAULT 'Common'"),
        ("mis_upload_timestamp", "TIMESTAMP",              "DATETIME"),
        ("mis_uploaded_by_id",   "INTEGER",                "INTEGER"),
        ("mis_filename",         "TEXT",                   "TEXT"),
        ("department",           "TEXT DEFAULT 'General Operations'", "TEXT DEFAULT 'General Operations'"),
    ]

    with engine.connect() as conn:
        for col_name, pg_type, sqlite_type in COLUMNS_TO_ADD:
            if col_name in existing_columns:
                print(f"  -> '{col_name}' already exists. Skipping.")
                continue

            if dialect == "sqlite":
                stmt = f"ALTER TABLE material_assignments ADD COLUMN {col_name} {sqlite_type};"
            else:
                # Postgres supports IF NOT EXISTS on ADD COLUMN (v9.6+)
                # Strip FK clause for IF NOT EXISTS syntax, add separately
                base_type = pg_type.split(" REFERENCES")[0]
                stmt = (
                    f"ALTER TABLE material_assignments "
                    f"ADD COLUMN IF NOT EXISTS {col_name} {base_type};"
                )

            print(f"  -> Running: {stmt}")
            conn.execute(text(stmt))
            print(f"  -> Added '{col_name}' successfully.")

        conn.commit()

    print("\n✅ Patch complete! Restart your application on Render.")


if __name__ == "__main__":
    patch()
