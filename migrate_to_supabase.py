"""
migrate_to_supabase.py
======================
Run this ONCE on your PC to copy all data from your local
inventory.db (SQLite) into your live Supabase PostgreSQL database.

INSTRUCTIONS:
1. Install dependency:  pip install psycopg2-binary
2. Set your DATABASE_URL below (same one you put in Render)
3. Place this file in the same folder as your inventory.db
4. Run:  python migrate_to_supabase.py
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

# ============================================================
# STEP 1 — PASTE YOUR SUPABASE CONNECTION STRING HERE
# ⚠️  SECURITY WARNING: Never commit this file to version control
#     (git, GitHub, etc.) with a real password filled in.
#     After migration, delete this file or blank out the password.
# ============================================================
SUPABASE_URL = "postgresql://postgres.wmkvpcoctuimuimujocz:Eipl1234Inventory@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

# ============================================================
# STEP 2 — PATH TO YOUR LOCAL SQLITE FILE
# ============================================================
SQLITE_PATH = "inventory.db"   # Change to "backup_inventory_live.db" if needed


# ---- helpers ------------------------------------------------

def ts(val):
    """Ensure timestamp is a proper datetime or None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


def migrate():
    print("=" * 60)
    print("  EIPL SQLite → Supabase Migration")
    print("=" * 60)

    # Open SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sc = sqlite_conn.cursor()

    # Open PostgreSQL
    pg_conn = psycopg2.connect(SUPABASE_URL)
    pg_conn.autocommit = False
    pc = pg_conn.cursor()

    try:
        # ------------------------------------------------
        # 1. USERS
        # ------------------------------------------------
        sc.execute("SELECT * FROM users")
        users = [dict(r) for r in sc.fetchall()]
        if users:
            execute_values(pc, """
                INSERT INTO users (id, username, hashed_password, role, full_name, designation, workstation_location)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(u['id'], u['username'], u['hashed_password'], u['role'],
                   u['full_name'], u['designation'], u['workstation_location']) for u in users])
            print(f"✅ users          — {len(users)} rows migrated")
        
        # Reset sequence so new users don't conflict
        pc.execute("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1))")

        # ------------------------------------------------
        # 2. ITEMS
        # ------------------------------------------------
        sc.execute("SELECT * FROM items")
        items = [dict(r) for r in sc.fetchall()]
        if items:
            execute_values(pc, """
                INSERT INTO items (id, item_code, name, category, description, supplier, storage_site, price, current_stock, minimum_stock)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(i['id'], i['item_code'], i['name'], i['category'], i['description'],
                   i['supplier'], i['storage_site'], i['price'], i['current_stock'], i['minimum_stock']) for i in items])
            print(f"✅ items           — {len(items)} rows migrated")
        
        pc.execute("SELECT setval('items_id_seq', COALESCE((SELECT MAX(id) FROM items), 1))")

        # ------------------------------------------------
        # 3. EMPLOYEES
        # ------------------------------------------------
        sc.execute("SELECT * FROM employees")
        employees = [dict(r) for r in sc.fetchall()]
        if employees:
            execute_values(pc, """
                INSERT INTO employees (id, name, role_title, location, contact)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(e['id'], e['name'], e['role_title'], e['location'], e['contact']) for e in employees])
            print(f"✅ employees       — {len(employees)} rows migrated")
        
        pc.execute("SELECT setval('employees_id_seq', COALESCE((SELECT MAX(id) FROM employees), 1))")

        # ------------------------------------------------
        # 4. PROCUREMENT REQUESTS
        # ------------------------------------------------
        sc.execute("SELECT * FROM procurement_requests")
        preqs = [dict(r) for r in sc.fetchall()]
        if preqs:
            execute_values(pc, """
                INSERT INTO procurement_requests (id, item_id, quantity, total_estimated_cost, requested_by_id, status, department, timestamp, is_new_item, new_item_name, detailed_specification)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(p['id'], p['item_id'], p['quantity'], p['total_estimated_cost'],
                   p['requested_by_id'], p['status'], p['department'], ts(p['timestamp']),
                   bool(p['is_new_item']), p['new_item_name'], p['detailed_specification']) for p in preqs])
            print(f"✅ procurement_requests — {len(preqs)} rows migrated")
        
        pc.execute("SELECT setval('procurement_requests_id_seq', COALESCE((SELECT MAX(id) FROM procurement_requests), 1))")

        # ------------------------------------------------
        # 5. MATERIAL ASSIGNMENTS
        # ------------------------------------------------
        sc.execute("SELECT * FROM material_assignments")
        massigns = [dict(r) for r in sc.fetchall()]
        if massigns:
            execute_values(pc, """
                INSERT INTO material_assignments (id, item_id, quantity, uom, issued_to, issued_by, department, remarks, timestamp, custodian, mis_filename, mis_uploaded_by_id, mis_upload_timestamp)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(m['id'], m['item_id'], m['quantity'], m['uom'], m['issued_to'],
                   m['issued_by'], m['department'], m['remarks'], ts(m['timestamp']),
                   m['custodian'], m['mis_filename'], m['mis_uploaded_by_id'],
                   ts(m['mis_upload_timestamp'])) for m in massigns])
            print(f"✅ material_assignments — {len(massigns)} rows migrated")
        
        pc.execute("SELECT setval('material_assignments_id_seq', COALESCE((SELECT MAX(id) FROM material_assignments), 1))")

        # ------------------------------------------------
        # 6. TRANSACTIONS
        # ------------------------------------------------
        sc.execute("SELECT * FROM transactions")
        txns = [dict(r) for r in sc.fetchall()]
        if txns:
            execute_values(pc, """
                INSERT INTO transactions (id, item_id, type, quantity, total_value, user_id, timestamp)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(t['id'], t['item_id'], t['type'], t['quantity'],
                   t['total_value'], t['user_id'], ts(t['timestamp'])) for t in txns])
            print(f"✅ transactions    — {len(txns)} rows migrated")
        
        pc.execute("SELECT setval('transactions_id_seq', COALESCE((SELECT MAX(id) FROM transactions), 1))")

        # ------------------------------------------------
        # 7. MATERIAL REQUESTS
        # ------------------------------------------------
        sc.execute("SELECT * FROM material_requests")
        mreqs = [dict(r) for r in sc.fetchall()]
        if mreqs:
            execute_values(pc, """
                INSERT INTO material_requests (id, item_id, quantity, total_estimated_cost, requested_by_id, status, department, timestamp, is_new_item, new_item_name, detailed_specification)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(m['id'], m['item_id'], m['quantity'], m['total_estimated_cost'],
                   m['requested_by_id'], m['status'], m['department'], ts(m['timestamp']),
                   bool(m['is_new_item']) if m['is_new_item'] is not None else False,
                   m['new_item_name'], m['detailed_specification']) for m in mreqs])
            print(f"✅ material_requests — {len(mreqs)} rows migrated")
        
        pc.execute("SELECT setval('material_requests_id_seq', COALESCE((SELECT MAX(id) FROM material_requests), 1))")

        # ------------------------------------------------
        # 8. GRN RECORDS
        # ------------------------------------------------
        sc.execute("SELECT * FROM grn_records")
        grns = [dict(r) for r in sc.fetchall()]
        if grns:
            execute_values(pc, """
                INSERT INTO grn_records (id, item_id, quantity, uom, received_by, grn_filename, uploaded_by_id, timestamp)
                VALUES %s
                ON CONFLICT (id) DO NOTHING
            """, [(g['id'], g['item_id'], g['quantity'], g['uom'], g['received_by'],
                   g['grn_filename'], g['uploaded_by_id'], ts(g['timestamp'])) for g in grns])
            print(f"✅ grn_records     — {len(grns)} rows migrated")
        
        pc.execute("SELECT setval('grn_records_id_seq', COALESCE((SELECT MAX(id) FROM grn_records), 1))")

        # ------------------------------------------------
        # COMMIT ALL
        # ------------------------------------------------
        pg_conn.commit()
        print()
        print("=" * 60)
        print("  ✅ Migration complete! All data is now in Supabase.")
        print("  Open your live app — all your data will be there.")
        print("=" * 60)

    except Exception as e:
        pg_conn.rollback()
        print()
        print(f"❌ Migration failed: {e}")
        print("   No data was changed. Fix the error and try again.")
        raise

    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    if "YOUR_PASSWORD" in SUPABASE_URL:
        print("❌ ERROR: You forgot to set your Supabase password in the script!")
        print("   Open migrate_to_supabase.py and replace YOUR_PASSWORD on line 19.")
    else:
        migrate()
