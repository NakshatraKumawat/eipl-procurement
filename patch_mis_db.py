"""
patch_mis_db.py
---------------
Run this ONCE on any existing inventory.db to add the new
MIS and department columns to the material_assignments table.
"""
import sqlite3, os

DB_PATH = "inventory.db"

if not os.path.exists(DB_PATH):
    print(f"Error: '{DB_PATH}' not found in this folder.")
else:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("Patching material_assignments table...")

    migrations = [
        ("department",           "TEXT DEFAULT 'General Operations'"),
        ("mis_filename",         "TEXT"),
        ("mis_uploaded_by_id",   "INTEGER"),
        ("mis_upload_timestamp", "DATETIME"),
    ]

    for col, definition in migrations:
        try:
            cursor.execute(f"ALTER TABLE material_assignments ADD COLUMN {col} {definition};")
            print(f"  -> Added '{col}' successfully.")
        except sqlite3.OperationalError:
            print(f"  -> '{col}' already exists. Skipping.")

    conn.commit()
    conn.close()
    print("\nPatch complete! Restart your application.")
