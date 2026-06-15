"""
migrate_assets.py
==================
One-time backfill for Fixed Assets and Equipments serial tracking.

What it does
------------
For every item you reclassify to category "Fixed Assets and Equipments", this
script creates one AssetUnit per existing unit of stock, with auto-generated
serial numbers in the form <ITEM_CODE>-001, <ITEM_CODE>-002, ...

Items kept as "Consumables" or "Tools and Tackles" are not touched.
Items that already have an asset register are not duplicated.

Run this once, after deploying the updated models.py / app.py:
    python migrate_assets.py

Two usage modes
---------------
1) Interactive (default): lists all items and lets you type reclassifications.
2) Scripted: pass a JSON file path with a
   {"<item_code>": "Fixed Assets and Equipments", ...} mapping:
       python migrate_assets.py reclassify.json

After running, you can edit serial numbers in your database to match real
asset tags.
"""
import sys
import json
from database import engine, SessionLocal
import models


TRACKED_CATEGORY = "Fixed Assets and Equipments"


def auto_serial(item_code, n):
    return "%s-%03d" % (item_code, n)


def backfill_item(db, item, target_category):
    if target_category != TRACKED_CATEGORY:
        return 0
    item.category = target_category
    existing = db.query(models.AssetUnit).filter(models.AssetUnit.item_id == item.id).count()
    target = item.current_stock or 0
    if existing >= target:
        return 0
    next_n = existing + 1
    created = 0
    while created < (target - existing):
        candidate = auto_serial(item.item_code, next_n)
        if not db.query(models.AssetUnit).filter(models.AssetUnit.serial_no == candidate).first():
            db.add(models.AssetUnit(item_id=item.id, serial_no=candidate, status="In Stock"))
            created += 1
        next_n += 1
    return created


def interactive_select(items):
    print("\nCurrent catalog:")
    print("  %4s  %-16s  %-35s  STOCK  CATEGORY" % ("ID", "CODE", "NAME"))
    print("  " + "-" * 80)
    for it in items:
        cat = it.category or "Consumables"
        name = (it.name or "")[:33]
        print("  %4d  %-16s  %-35s  %5d  %s" % (it.id, it.item_code, name, it.current_stock or 0, cat))
    print("\nEnter reclassifications, one per line.")
    print("Format:  <id_or_code> " + TRACKED_CATEGORY)
    print("Blank line to finish. Example:")
    print("    EIPLJBRI Fixed Assets and Equipments\n")
    by_id = {it.id: it for it in items}
    by_code = {it.item_code: it for it in items}
    plan = {}
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            break
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            print("  Expected: <id_or_code> <category>")
            continue
        key, cat = parts[0], parts[1].strip()
        if cat != TRACKED_CATEGORY:
            print("  Category must be exactly %r for serial tracking (got %r)." % (TRACKED_CATEGORY, cat))
            continue
        it = by_id.get(int(key)) if key.isdigit() else by_code.get(key.upper())
        if not it:
            print("  No item with id/code %r." % key)
            continue
        plan[it.id] = cat
        print("  queued: %s (%s) -> %s" % (it.item_code, it.name, cat))
    return plan


def main():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        items = db.query(models.Item).order_by(models.Item.id).all()
        if len(sys.argv) > 1:
            with open(sys.argv[1]) as f:
                spec = json.load(f)
            by_code = {it.item_code: it for it in items}
            plan = {}
            for code, cat in spec.items():
                it = by_code.get(code.upper())
                if not it:
                    print("WARN: item_code %r not found, skipping" % code)
                    continue
                plan[it.id] = cat
        else:
            plan = interactive_select(items)

        if not plan:
            print("No reclassifications. Exiting without changes.")
            return

        print("\nApplying changes...")
        total_units = 0
        total_items = 0
        for item_id, cat in plan.items():
            it = db.query(models.Item).filter(models.Item.id == item_id).first()
            if not it:
                continue
            created = backfill_item(db, it, cat)
            total_items += 1
            total_units += created
            print("  %-16s -> %s  (+%d asset units)" % (it.item_code, cat, created))
        db.commit()
        print("\nDone. Reclassified %d item(s), created %d AssetUnit row(s)." % (total_items, total_units))
        print("Click the 'Serials' button on tracked items to view the register.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
