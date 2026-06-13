"""
migrate_item_lots.py
=====================
One-time migration to introduce multi-vendor / multi-price stock lots.

What it does:
1. Creates the new `item_lots` table (if it doesn't already exist —
   models.Base.metadata.create_all() on app startup also does this,
   so this step is usually a no-op safety net).
2. For every existing Item with current_stock > 0 that doesn't yet
   have any lot rows, creates ONE lot using that item's existing
   vendor (`supplier`) and `price`, with quantity = current_stock.
   This preserves your current stock totals exactly — it just gives
   them a starting "batch" so FIFO outward issuing has something to
   consume from.

After this runs, new Inward transactions will create additional lots
per (vendor, price) as described, and the inventory table's "Total
Quantity" continues to equal the sum of all lots for that item code.

Run this ONCE after deploying the updated app.py / models.py:
    python migrate_item_lots.py
"""

from database import engine, SessionLocal
import models
from sqlalchemy import inspect

def migrate():
    # Ensure the item_lots table exists
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        items = db.query(models.Item).all()
        created = 0
        skipped_existing = 0
        skipped_zero = 0

        for item in items:
            existing_lot = db.query(models.ItemLot).filter(
                models.ItemLot.item_id == item.id
            ).first()
            if existing_lot:
                skipped_existing += 1
                continue

            qty = item.current_stock or 0
            if qty <= 0:
                skipped_zero += 1
                continue

            db.add(models.ItemLot(
                item_id=item.id,
                vendor=item.supplier or "Approved Vendor",
                price=item.price or 0.0,
                quantity=qty,
            ))
            created += 1

        db.commit()
        print(f"Done. Created {created} initial lot(s).")
        print(f"Skipped {skipped_existing} item(s) that already had lots.")
        print(f"Skipped {skipped_zero} item(s) with zero/blank current_stock.")
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
