import csv
import hashlib
import random
import datetime as _ist_dt
from io import StringIO
from fastapi import FastAPI, Form, Depends, Cookie, Response, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

import models
import templates
from database import engine, get_db, SessionLocal

# Force absolute structural table synchronization on startup
models.Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------
# IST (INDIA STANDARD TIME) DISPLAY HELPERS
# -------------------------------------------------------------
# All timestamps are stored in the database as naive UTC datetimes
# (via datetime.utcnow() defaults). For display anywhere in the UI,
# convert to IST (UTC+5:30) before formatting.
IST_OFFSET = _ist_dt.timedelta(hours=5, minutes=30)


def to_ist(dt):
    """Convert a naive UTC datetime to a naive IST datetime for display.
    Returns None if dt is None."""
    if dt is None:
        return None
    return dt + IST_OFFSET


def fmt_ist(dt, fmt="%d-%m-%Y %H:%M"):
    """Format a stored (naive UTC) datetime as IST. Returns '' if dt is None."""
    if dt is None:
        return ""
    return to_ist(dt).strftime(fmt)

# -------------------------------------------------------------
# MULTI-VENDOR LOT / FIFO HELPERS
# -------------------------------------------------------------
# Each Item can have multiple ItemLot rows — one per (vendor, price)
# combination. Item.current_stock is kept as a cached running total
# equal to the sum of all of that item's lot quantities, so existing
# code that reads current_stock for display/low-stock checks keeps
# working unchanged.

_LOT_PRICE_EPS = 0.005  # treat prices within half a paisa as the same lot


def add_to_lot(db: Session, item: "models.Item", vendor: str, price: float, quantity: int, received_at=None):
    """Add `quantity` units to the matching (item, vendor, price) lot,
    creating it if it doesn't exist yet. Also bumps item.current_stock."""
    import datetime as _dt
    if quantity <= 0:
        return
    vendor = (vendor or item.supplier or "Approved Vendor").strip() or "Approved Vendor"
    price = float(price) if price is not None else 0.0

    lot = db.query(models.ItemLot).filter(
        models.ItemLot.item_id == item.id,
        models.ItemLot.vendor == vendor,
        models.ItemLot.price.between(price - _LOT_PRICE_EPS, price + _LOT_PRICE_EPS)
    ).first()

    if lot:
        lot.quantity += quantity
    else:
        db.add(models.ItemLot(
            item_id=item.id, vendor=vendor, price=price,
            quantity=quantity, received_at=received_at or _dt.datetime.utcnow()
        ))

    item.current_stock = (item.current_stock or 0) + quantity


def consume_fifo(db: Session, item: "models.Item", quantity: int):
    """Consume `quantity` units from this item's lots, oldest first.
    Returns the total cost (sum of qty_taken * lot.price) of the units
    consumed. Reduces item.current_stock accordingly. Caller is
    responsible for checking sufficient stock beforehand; if lots run
    out early, the remainder is costed at the item's current `price`."""
    remaining = quantity
    total_cost = 0.0

    lots = db.query(models.ItemLot).filter(
        models.ItemLot.item_id == item.id,
        models.ItemLot.quantity > 0
    ).order_by(models.ItemLot.received_at.asc(), models.ItemLot.id.asc()).all()

    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.quantity, remaining)
        if take > 0:
            lot.quantity -= take
            total_cost += take * (lot.price or 0.0)
            remaining -= take

    if remaining > 0:
        # Lots didn't cover the full quantity (e.g. legacy stock with no
        # lot records yet) — cost the shortfall at the item's list price.
        total_cost += remaining * (item.price or 0.0)
        remaining = 0

    item.current_stock = max(0, (item.current_stock or 0) - quantity)
    return total_cost


def reconcile_stock_delta(db: Session, item: "models.Item", delta: int):
    """Apply a manual stock adjustment (e.g. from the Edit Item modal) of
    `delta` units (positive or negative) to the lot ledger, keeping
    sum(lot.quantity) == item.current_stock."""
    if delta == 0:
        return
    if delta > 0:
        add_to_lot(db, item, "Manual Adjustment", item.price or 0.0, delta)
    else:
        consume_fifo(db, item, -delta)


def build_txn_logs(db: Session, items):
    """Build per-item transaction logs used by both the Material Flow view
    and the merged Inventory Configuration table.

    Each inward (IN) row carries its OWN vendor and per-unit price taken
    from its GRN record (not the item's moving catalog value), so a later
    inward at a different vendor/price no longer rewrites historical rows.

    Price Diff / Percentage Diff are computed batch-over-batch: each IN is
    compared to the immediately preceding IN of the same item, so they show
    how the newly entered price changed versus the previous purchase.
    Returns {item_id: [entry, ...]} sorted newest-first.
    """
    import datetime as _dt
    transactions = db.query(models.Transaction).all()
    assignments = db.query(models.MaterialAssignment).all()
    grns = db.query(models.GRNRecord).all()
    item_by_id = {i.id: i for i in items}
    _MIN = _dt.datetime.min

    # Legacy fallback: per-unit price by (item_id, minute) from IN transactions
    txn_price_lookup = {}
    for t in transactions:
        if t.type == "IN" and t.quantity and t.quantity > 0 and t.total_value:
            per_unit = round(t.total_value / t.quantity, 2)
            ts_str = fmt_ist(t.timestamp)
            txn_price_lookup.setdefault(t.item_id, {})[ts_str] = per_unit

    # Vendor recovery for legacy GRNs (no stored vendor): the actual vendor
    # for each batch was recorded in item_lots at inward time. We match a GRN
    # to its lot by price so old rows show their ORIGINAL vendor instead of
    # the item's current catalog supplier. Include consumed (qty 0) lots too,
    # since they still hold the vendor history.
    lots_by_item = {}
    for lot in db.query(models.ItemLot).all():
        lots_by_item.setdefault(lot.item_id, []).append(lot)

    def _recover_vendor(item_id, unit_price, when, fallback):
        lots = lots_by_item.get(item_id)
        if not lots:
            return fallback
        # candidates whose price matches this batch's per-unit price
        cands = [l for l in lots if abs((l.price or 0.0) - (unit_price or 0.0)) <= 0.01]
        if not cands:
            return fallback
        # prefer the lot that existed by this GRN's time, closest in time
        prior = [l for l in cands if (l.received_at or _MIN) <= (when or _MIN)]
        pool = prior if prior else cands
        best = min(pool, key=lambda l: abs(((l.received_at or _MIN) - (when or _MIN)).total_seconds()))
        return best.vendor or fallback

    # IN entries from GRNs (keep real datetime for correct chronological sort)
    in_entries = {}
    for g in grns:
        item_obj = item_by_id.get(g.item_id)
        catalog_price = (item_obj.price if item_obj else 0.0) or 0.0
        catalog_vendor = (item_obj.supplier if item_obj else "\u2014") or "\u2014"
        gdt = g.timestamp or _MIN
        grn_date = fmt_ist(g.timestamp)
        unit_price = getattr(g, "unit_price", None)
        if unit_price is None:
            unit_price = txn_price_lookup.get(g.item_id, {}).get(grn_date, catalog_price)
        # Use the GRN's own stored vendor; for legacy rows, recover it from the
        # matching lot by price, and only then fall back to the catalog vendor.
        vendor = getattr(g, "vendor", None)
        if not vendor:
            vendor = _recover_vendor(g.item_id, unit_price, gdt, catalog_vendor)
        person = getattr(g, "received_by", "") or (g.uploader.username if g.uploader else "\u2014")
        entry = {
            "date": grn_date, "type": "IN", "qty": g.quantity,
            "uom": g.uom or "Nos", "person": person or "\u2014", "direction": "IN",
            "vendor": vendor, "price": round(unit_price or 0.0, 2),
            "grn_no": getattr(g, "grn_no", None) or "\u2014",
            "challan_no": getattr(g, "challan_no", None) or "\u2014",
            "serial_no": "\u2014",
            "price_diff": None, "pct_diff": None,
        }
        in_entries.setdefault(g.item_id, []).append((gdt, entry))

    # Compute batch-over-batch diffs per item
    for lst in in_entries.values():
        lst.sort(key=lambda x: x[0])  # oldest first
        prev_price = None
        for _dtk, e in lst:
            if prev_price is not None and prev_price > 0:
                diff = round(e["price"] - prev_price, 2)
                if abs(diff) > 0.01:
                    e["price_diff"] = diff
                    e["pct_diff"] = round((diff / prev_price) * 100, 2)
            prev_price = e["price"]

    # OUT entries from material assignments
    # OUT entries (issues) and RETURN entries from material_assignments.
    # For serial-tracked items, fetch the serial via asset_unit_id link.
    unit_serials = {u.id: (u.serial_no or "\u2014") for u in db.query(models.AssetUnit).all()}
    out_entries = {}
    for a in assignments:
        adt = a.timestamp or _MIN
        is_ret = bool(getattr(a, "is_return", False))
        serial = "\u2014"
        aid = getattr(a, "asset_unit_id", None)
        if aid:
            serial = unit_serials.get(aid, "\u2014")
        if is_ret:
            entry = {
                "date": fmt_ist(a.timestamp),
                "type": "RETURN", "qty": a.quantity, "uom": a.uom or "Nos",
                "person": a.issued_to or "\u2014", "direction": "IN",
                "serial_no": serial,
                "is_return": True,
            }
        else:
            entry = {
                "date": fmt_ist(a.timestamp),
                "type": "OUT", "qty": a.quantity, "uom": a.uom or "Nos",
                "person": a.issued_to or "\u2014", "direction": "OUT",
                "serial_no": serial,
            }
        out_entries.setdefault(a.item_id, []).append((adt, entry))

    logs = {}
    for iid in set(in_entries) | set(out_entries):
        combined = in_entries.get(iid, []) + out_entries.get(iid, [])
        combined.sort(key=lambda x: x[0], reverse=True)  # newest first
        logs[iid] = [e for _dtk, e in combined]
    return logs


app = FastAPI(title="EIPL Enterprise Procurement Framework")

# -------------------------------------------------------------
# ASSET CLASS CATEGORIES
# -------------------------------------------------------------
ASSET_CLASSES = ["Fixed Assets and Equipments", "Consumables", "Tools and Tackles"]
DEFAULT_ASSET_CLASS = "Consumables"
# Only items in TRACKED_CATEGORIES are serial-tracked (one AssetUnit per physical thing).
TRACKED_CATEGORIES = ("Fixed Assets and Equipments",)


def is_tracked(item_or_category) -> bool:
    """True if the item (or category string) is serial-tracked.
    Accepts either an Item instance or a raw category string."""
    cat = item_or_category if isinstance(item_or_category, str) else getattr(item_or_category, "category", None)
    return cat in TRACKED_CATEGORIES


def category_options_html(selected=None):
    """Return <option> tags for the asset class dropdown, marking `selected`."""
    sel = selected if selected in ASSET_CLASSES else None
    opts = ""
    for c in ASSET_CLASSES:
        is_sel = " selected" if (sel == c) else ""
        opts += f'<option value="{c}"{is_sel}>{c}</option>'
    return opts



# Serve static assets (company logo etc.) from ./static folder
import os as _os
from fastapi.staticfiles import StaticFiles
_os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# -------------------------------------------------------------
# 1. FIXED EXPLICIT ROUTE FOR FAVICON TO BYPASS 404 EXCEPTIONS
# -------------------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


# -------------------------------------------------------------
# 2. FULLY FIXED ASYNC EXCEPTION HANDLER
# -------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    if exc.status_code == 404 and not request.cookies.get("session_user"):
        return RedirectResponse(url="/login", status_code=303)
    return await http_exception_handler(request, exc)


def hash_password(password: str) -> str:
    """Standardized SHA-256 password hashing for system security."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def run_structural_database_migrations():
    """Self-healing migration engine to clean up schema columns in existing databases."""
    # --- Phase 1: Inspect ALL tables while the connection is still open ---
    existing_cols_emp = []
    existing_cols_proc = []
    existing_cols_ma = []
    existing_cols_items = []

    try:
        from sqlalchemy import inspect as _inspect
        _insp = _inspect(engine)
        existing_cols_emp   = [col['name'] for col in _insp.get_columns('employees')]
        existing_cols_proc  = [col['name'] for col in _insp.get_columns('procurement_requests')]
        existing_cols_ma    = [col['name'] for col in _insp.get_columns('material_assignments')]
        existing_cols_items = [col['name'] for col in _insp.get_columns('items')]
    except Exception as e:
        print(f"[Migration] Schema inspection error: {e}")

    # --- Phase 2: Apply any missing ALTER TABLE statements ---
    try:
        with engine.connect() as _conn:
            if "location" not in existing_cols_emp:
                _conn.execute(text("ALTER TABLE employees ADD COLUMN location TEXT DEFAULT 'Not Specified'"))
            if "contact" not in existing_cols_emp:
                _conn.execute(text("ALTER TABLE employees ADD COLUMN contact TEXT DEFAULT 'Not Specified'"))
            if "department" not in existing_cols_proc:
                _conn.execute(text("ALTER TABLE procurement_requests ADD COLUMN department TEXT DEFAULT 'Operations'"))
            if "department" not in existing_cols_ma:
                _conn.execute(text("ALTER TABLE material_assignments ADD COLUMN department TEXT DEFAULT 'General Operations'"))
            if "mis_filename" not in existing_cols_ma:
                _conn.execute(text("ALTER TABLE material_assignments ADD COLUMN mis_filename TEXT"))
            if "mis_uploaded_by_id" not in existing_cols_ma:
                _conn.execute(text("ALTER TABLE material_assignments ADD COLUMN mis_uploaded_by_id INTEGER"))
            if "mis_upload_timestamp" not in existing_cols_ma:
                _conn.execute(text("ALTER TABLE material_assignments ADD COLUMN mis_upload_timestamp DATETIME"))
            if "uom" not in existing_cols_items:
                _conn.execute(text("ALTER TABLE items ADD COLUMN uom TEXT"))
            _conn.commit()
    except Exception as e:
        print(f"[Migration Adaptive Notice] Columns pre-aligned: {e}")

    # Ensure procurement_messages table exists (new feature)
    # Uses engine directly so DDL works on both SQLite and PostgreSQL
    try:
        with engine.connect() as _ddl_conn:
            if engine.dialect.name == "postgresql":
                _ddl_conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS procurement_messages (
                        id SERIAL PRIMARY KEY,
                        request_id INTEGER REFERENCES procurement_requests(id),
                        sender_id INTEGER REFERENCES users(id),
                        message TEXT,
                        timestamp TIMESTAMP
                    )
                """))
            else:
                _ddl_conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS procurement_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id INTEGER REFERENCES procurement_requests(id),
                        sender_id INTEGER REFERENCES users(id),
                        message TEXT,
                        timestamp DATETIME
                    )
                """))
            # Add received_by to grn_records if missing
            try:
                _ddl_conn.execute(text("ALTER TABLE grn_records ADD COLUMN received_by TEXT"))
            except Exception:
                pass  # Column already exists
            # Per-batch vendor + price so the transaction log keeps each
            # inward's own vendor/price instead of the moving catalog value
            try:
                _ddl_conn.execute(text("ALTER TABLE grn_records ADD COLUMN vendor TEXT"))
            except Exception:
                pass
            try:
                _ddl_conn.execute(text("ALTER TABLE grn_records ADD COLUMN unit_price DOUBLE PRECISION"
                                       if engine.dialect.name == "postgresql"
                                       else "ALTER TABLE grn_records ADD COLUMN unit_price REAL"))
            except Exception:
                pass
            # GRN / Challan reference numbers captured at inward time
            try:
                _ddl_conn.execute(text("ALTER TABLE grn_records ADD COLUMN grn_no TEXT"))
            except Exception:
                pass
            try:
                _ddl_conn.execute(text("ALTER TABLE grn_records ADD COLUMN challan_no TEXT"))
            except Exception:
                pass
            # Admin-entered procurement pricing (vendor + rate) that gates ordering
            try:
                _ddl_conn.execute(text("ALTER TABLE procurement_requests ADD COLUMN vendor TEXT"))
            except Exception:
                pass
            try:
                _ddl_conn.execute(text("ALTER TABLE procurement_requests ADD COLUMN unit_price DOUBLE PRECISION"
                                       if engine.dialect.name == "postgresql"
                                       else "ALTER TABLE procurement_requests ADD COLUMN unit_price REAL"))
            except Exception:
                pass

            # --- Store uploaded file bytes in the shared DB so they are
            #     available across all devices (local disk is per-machine
            #     and ephemeral on Render). BYTEA on Postgres, BLOB on SQLite. ---
            _blob_type = "BYTEA" if engine.dialect.name == "postgresql" else "BLOB"
            try:
                _ddl_conn.execute(text(f"ALTER TABLE grn_records ADD COLUMN grn_filedata {_blob_type}"))
            except Exception:
                pass  # Column already exists
            try:
                _ddl_conn.execute(text(f"ALTER TABLE material_assignments ADD COLUMN mis_filedata {_blob_type}"))
            except Exception:
                pass  # Column already exists
            # --- Return-to-Store columns on material_assignments (same table) ---
            _bool_default = "BOOLEAN DEFAULT FALSE" if engine.dialect.name == "postgresql" else "BOOLEAN DEFAULT 0"
            try:
                _ddl_conn.execute(text(f"ALTER TABLE material_assignments ADD COLUMN is_return {_bool_default}"))
            except Exception:
                pass
            try:
                _ddl_conn.execute(text("ALTER TABLE material_assignments ADD COLUMN return_filename TEXT"))
            except Exception:
                pass
            try:
                _ddl_conn.execute(text(f"ALTER TABLE material_assignments ADD COLUMN return_filedata {_blob_type}"))
            except Exception:
                pass
            # --- ASSET CLASS CATEGORY columns ---
            try:
                _ddl_conn.execute(text(f"ALTER TABLE items ADD COLUMN category TEXT DEFAULT '{DEFAULT_ASSET_CLASS}'"))
            except Exception:
                pass
            try:
                _ddl_conn.execute(text("ALTER TABLE procurement_requests ADD COLUMN category TEXT"))
            except Exception:
                pass
            # --- Fixed Assets and Equipments per-unit tracking ---
            try:
                _ddl_conn.execute(text("ALTER TABLE material_assignments ADD COLUMN asset_unit_id INTEGER"))
            except Exception:
                pass
            _ddl_conn.commit()
    except Exception as e:
        print(f"[Migration] procurement_messages: {e}")


run_structural_database_migrations()


def seed_system_data():
    """Populates basic master data if tables are freshly generated."""
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add_all([
                models.User(
                    username="admin",
                    hashed_password=hash_password("password123"),
                    role="Admin",
                    full_name="Rajesh Kumar Sharma",
                    designation="Project General Manager",
                    workstation_location="Corporate HQ - New Delhi"
                ),
                models.User(
                    username="staff",
                    hashed_password=hash_password("password123"),
                    role="Staff",
                    full_name="Amit Kumar Verma",
                    designation="Store Logistics Officer",
                    workstation_location="Okhla Logistics Hub"
                )
            ])
            db.commit()
        if db.query(models.Employee).count() == 0:
            db.add_all([
                models.Employee(name="Piyush Bhatia", role_title="Sr. Manager- Commercial", contact="9926306363", location="Corporate HQ"),
                models.Employee(name="Biswajit Pradhan", role_title="Engineer", contact="9348653235", location="Udaipur Site Base")
            ])
            db.commit()
    finally:
        db.close()


seed_system_data()


def get_current_user(session_user: str = Cookie(None), db: Session = Depends(get_db)):
    """Cookie-based identity validation session guard."""
    if not session_user:
        return None
    return db.query(models.User).filter(models.User.username == session_user).first()


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return templates.LOGIN_HTML


@app.post("/login")
def do_login(response: Response, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(
        models.User.username == username.strip().lower()).first()
    if not user or user.hashed_password != hash_password(password):
        return HTMLResponse("<script>alert('Invalid credentials!'); window.location='/login';</script>")

    res = RedirectResponse(url="/", status_code=303)
    res.set_cookie(key="session_user", value=user.username)
    return res


@app.get("/logout")
def do_logout():
    res = RedirectResponse(url="/login", status_code=303)
    res.delete_cookie("session_user")
    return res


@app.post("/transaction")
async def create_transaction(
    item_id: str = Form(...),              # "NEW_INWARD_ITEM" or existing item id
    quantity: int = Form(...),
    uom: str = Form(...),
    grn_no: str = Form(None),
    challan_no: str = Form(None),
    new_item_name: str = Form(None),
    new_item_code: str = Form(None),
    new_item_category: str = Form(None),       # used when creating a new item
    serial_numbers: str = Form(None),          # newline/comma-separated for tracked items
    site: str = Form(None),
    grn_file: UploadFile = File(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    if not grn_file or not grn_file.filename:
        return HTMLResponse("<script>alert('GRN Upload is mandatory before recording an Inward Transaction.'); window.history.back();</script>")

    import os, datetime as _dt
    grn_dir = "grn_uploads"
    os.makedirs(grn_dir, exist_ok=True)
    timestamp_str = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    placed_orders = []

    if item_id == "NEW_INWARD_ITEM":
        if not new_item_name or not new_item_code:
            return HTMLResponse("<script>alert('Item Name and Item Code are required for a new item.'); window.history.back();</script>")
        clean_code = new_item_code.strip().upper()
        existing = db.query(models.Item).filter(models.Item.item_code == clean_code).first()
        if existing:
            return HTMLResponse(f"<script>alert('Item Code {clean_code} already exists in catalog. Please use Search & Select for existing items.'); window.history.back();</script>")
        cat = (new_item_category or "").strip()
        if cat not in ASSET_CLASSES:
            cat = DEFAULT_ASSET_CLASS
        new_item = models.Item(
            name=new_item_name.strip(),
            item_code=clean_code,
            category=cat,
            current_stock=0,
            price=0.0,
            supplier="Approved Vendor",
            storage_site=site.strip() if site else "Store Yard",
            uom=uom,
            minimum_stock=0
        )
        db.add(new_item)
        db.flush()
        item = new_item
        lot_vendor = item.supplier or "Approved Vendor"
        lot_price = item.price or 0.0
    else:
        item = db.query(models.Item).filter(models.Item.id == int(item_id)).first()
        if not item:
            return HTMLResponse("<script>alert('Item not found.'); window.location='/';</script>")
        if not item.uom:
            item.uom = uom
        uom = item.uom

        placed_orders = db.query(models.ProcurementRequest).filter(
            models.ProcurementRequest.item_id == item.id,
            models.ProcurementRequest.status == "Order Placed"
        ).order_by(models.ProcurementRequest.timestamp.asc()).all()
        source_order = placed_orders[0] if placed_orders else None

        if source_order and source_order.vendor:
            lot_vendor = source_order.vendor
        else:
            lot_vendor = item.supplier or "Approved Vendor"
        if source_order and source_order.unit_price is not None:
            lot_price = float(source_order.unit_price)
        else:
            lot_price = item.price or 0.0

        item.supplier = lot_vendor
        item.price = lot_price

    # --- SERIAL-TRACKED PATH (Fixed Assets and Equipments) ---
    serial_list = []
    if is_tracked(item):
        raw = (serial_numbers or "").replace(",", "\n")
        serial_list = [s.strip() for s in raw.split("\n") if s.strip()]
        if not serial_list:
            return HTMLResponse("<script>alert('Serial number(s) are required for Fixed Assets and Equipments. Enter one serial per line.'); window.history.back();</script>")
        if quantity != len(serial_list):
            return HTMLResponse(f"<script>alert('Quantity ({quantity}) must equal the number of serials provided ({len(serial_list)}).'); window.history.back();</script>")
        if len(set(serial_list)) != len(serial_list):
            return HTMLResponse("<script>alert('Duplicate serials within this entry. Each serial must be unique.'); window.history.back();</script>")
        existing_serials = {row[0] for row in db.query(models.AssetUnit.serial_no).filter(
            models.AssetUnit.serial_no.in_(serial_list)
        ).all()}
        dup = [s for s in serial_list if s in existing_serials]
        if dup:
            return HTMLResponse(f"<script>alert('These serial numbers already exist: {', '.join(dup[:5])}'); window.history.back();</script>")
        now = _dt.datetime.utcnow()
        for s in serial_list:
            db.add(models.AssetUnit(item_id=item.id, serial_no=s, status="In Stock", acquired_at=now))
        item.current_stock = (item.current_stock or 0) + len(serial_list)
    else:
        add_to_lot(db, item, lot_vendor, lot_price, quantity)

    item_unit_price = lot_price

    received_by_name = current_user.full_name or current_user.username

    safe_filename = f"GRN_{item.item_code}_{timestamp_str}_{grn_file.filename.replace(' ', '_')}"
    grn_path = os.path.join(grn_dir, safe_filename)
    contents = await grn_file.read()
    with open(grn_path, "wb") as f:
        f.write(contents)

    db.add(models.Transaction(
        item_id=item.id,
        type="IN",
        quantity=quantity,
        user_id=current_user.id,
        total_value=float(quantity * item_unit_price)
    ))

    db.add(models.GRNRecord(
        item_id=item.id,
        quantity=quantity,
        uom=uom,
        received_by=received_by_name,
        vendor=lot_vendor,
        unit_price=item_unit_price,
        grn_no=(grn_no.strip() if grn_no else None),
        challan_no=(challan_no.strip() if challan_no else None),
        grn_filename=safe_filename,
        grn_filedata=contents,
        uploaded_by_id=current_user.id
    ))

    # Mark the placed order(s) for this item as Delivered
    for ord_req in placed_orders:
        ord_req.status = "Delivered"

    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/inward/bulk-template")
def inward_bulk_template(current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    from fastapi.responses import StreamingResponse
    import io
    csv_content = "item_code_or_NEW,item_name,quantity,uom,vendor,price,site\n"
    csv_content += "EIPL-ST-01,,50,Nos,Tata Steel,350.00,Udaipur Yard\n"
    csv_content += "NEW,Copper Cable 4mm,100,Mtr,Polycab,125.50,Store Room A\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=EIPL_Inward_Transaction_Template.csv"}
    )


@app.post("/inward/bulk-import")
async def inward_bulk_import(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    try:
        contents = await file.read()
        try:
            decoded = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = contents.decode('latin-1')
        lines = [l for l in decoded.splitlines() if l.strip() and not l.strip().startswith('#')]

        try:
            sample_data = "\n".join(lines[:5])
            dialect = csv.Sniffer().sniff(sample_data)
            if dialect.delimiter not in [',', ';', '\t', '|']:
                dialect.delimiter = ','
            reader = csv.DictReader(lines, dialect=dialect)
        except Exception:
            reader = csv.DictReader(lines)

        added_count = 0
        updated_count = 0

        for row in reader:
            if not row:
                continue
            clean_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k is not None}

            item_code_raw = clean_row.get("item_code_or_new") or clean_row.get("item_code") or ""
            item_name = clean_row.get("item_name") or clean_row.get("name") or ""
            qty_raw = clean_row.get("quantity") or clean_row.get("qty") or "0"
            uom = clean_row.get("uom") or "Nos"
            vendor = clean_row.get("vendor") or clean_row.get("supplier") or "Approved Vendor"
            price_raw = clean_row.get("price") or clean_row.get("rate") or "0.0"
            site = clean_row.get("site") or clean_row.get("storage_site") or "Store Yard"

            try:
                quantity = int(float(qty_raw))
                price = float(price_raw)
            except ValueError:
                continue

            if quantity <= 0:
                continue

            is_new = item_code_raw.strip().upper() == "NEW"

            if is_new:
                if not item_name:
                    continue
                import random, string as _string
                gen_code = "EIPL-" + ''.join(random.choices(_string.ascii_uppercase, k=2)) + "-" + ''.join(random.choices(_string.digits, k=2))
                new_item = models.Item(
                    name=item_name, item_code=gen_code, current_stock=0,
                    price=price, supplier=vendor, storage_site=site, uom=uom, minimum_stock=0
                )
                db.add(new_item)
                db.flush()
                add_to_lot(db, new_item, vendor, price, quantity)
                db.add(models.Transaction(item_id=new_item.id, type="IN", quantity=quantity, user_id=current_user.id, total_value=float(quantity * price)))
                db.add(models.GRNRecord(item_id=new_item.id, quantity=quantity, uom=uom,
                    received_by=current_user.full_name or current_user.username,
                    vendor=vendor, unit_price=price,
                    grn_filename="BULK_CSV_IMPORT", uploaded_by_id=current_user.id))
                added_count += 1
            else:
                clean_code = item_code_raw.strip().upper()
                if not clean_code:
                    continue
                item = db.query(models.Item).filter(models.Item.item_code == clean_code).first()
                if not item:
                    if not item_name:
                        continue
                    item = models.Item(name=item_name, item_code=clean_code, current_stock=0,
                        price=price, supplier=vendor, storage_site=site, uom=uom, minimum_stock=0)
                    db.add(item)
                    db.flush()
                    added_count += 1
                else:
                    if price > 0:
                        item.price = price
                    if vendor and vendor != "Approved Vendor":
                        item.supplier = vendor
                    if not item.uom:
                        item.uom = uom
                    uom = item.uom  # Use locked uom
                    updated_count += 1

                lot_vendor = vendor if (vendor and vendor != "Approved Vendor") else item.supplier
                lot_price = price if price > 0 else (item.price or 0.0)
                add_to_lot(db, item, lot_vendor, lot_price, quantity)
                db.add(models.Transaction(item_id=item.id, type="IN", quantity=quantity, user_id=current_user.id, total_value=float(quantity * item.price)))
                db.add(models.GRNRecord(item_id=item.id, quantity=quantity, uom=uom,
                    received_by=current_user.full_name or current_user.username,
                    vendor=lot_vendor, unit_price=lot_price,
                    grn_filename="BULK_CSV_IMPORT", uploaded_by_id=current_user.id))

        db.commit()
        return HTMLResponse(f"<script>alert('Bulk Inward Import Complete!\\nNew Items Added: {added_count}\\nExisting Items Updated: {updated_count}'); window.location='/';</script>")
    except Exception as e:
        db.rollback()
        return HTMLResponse(f"<script>alert('Import error: {str(e)}'); window.location='/';</script>")


@app.get("/grn/list", response_class=HTMLResponse)
def grn_list(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    grns = db.query(models.GRNRecord).order_by(models.GRNRecord.timestamp.desc()).all()
    rows = ""
    for g in grns:
        ts = fmt_ist(g.timestamp)
        ts_iso = fmt_ist(g.timestamp, "%Y-%m-%d")
        item_name = g.item.name if g.item else "Unknown Item"
        item_code = g.item.item_code if g.item else "—"
        uploader = g.uploader.username if g.uploader else "System"
        vendor = getattr(g, 'vendor', '') or '—'
        grn_no = getattr(g, 'grn_no', '') or '—'
        challan_no = getattr(g, 'challan_no', '') or '—'
        rows += f"""
        <tr class="border-b hover:bg-slate-50 text-xs grn-row"
            data-date="{ts_iso}" data-item="{item_name.lower()}" data-code="{item_code.lower()}"
            data-vendor="{vendor.lower()}" data-uploader="{uploader.lower()}" data-grn="{grn_no.lower()}">
            <td class="p-3 text-slate-500 font-mono whitespace-nowrap">{ts}</td>
            <td class="p-3 font-semibold text-slate-800">{item_name}</td>
            <td class="p-3 font-mono text-slate-500">{item_code}</td>
            <td class="p-3 text-center font-mono font-bold text-slate-700">{g.quantity} {g.uom}</td>
            <td class="p-3 text-slate-600">{vendor}</td>
            <td class="p-3 font-mono text-slate-500 text-center">{grn_no}</td>
            <td class="p-3 font-mono text-slate-500 text-center">{challan_no}</td>
            <td class="p-3 text-slate-500">{uploader}</td>
            <td class="p-3 text-right">
                <a href="/grn/download/{g.id}" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all">&#11015; Download</a>
            </td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>GRN Downloads - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>body{{font-family:'Inter',sans-serif;}}.filter-input{{font-size:11px;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;width:100%;box-sizing:border-box;}}
.filter-input:focus{{outline:none;border-color:#6366f1;background:#fff;}}</style>
</head>
<body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user, current_page='grn')}
<div class="flex-1 min-h-screen overflow-x-hidden p-6">
    <div class="max-w-7xl mx-auto">
        <div class="flex items-center justify-between mb-5">
            <div>
                <a href="/" class="text-indigo-600 text-xs font-bold hover:underline">&#8592; Back to Dashboard</a>
                <h1 class="text-xl font-black text-slate-900 mt-1">&#128196; GRN Download Centre</h1>
                <p class="text-xs text-slate-400 mt-0.5">Goods Received Notes — uploaded inward transaction records</p>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="exportGRN()" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-4 py-2 rounded-lg transition-all flex items-center gap-1.5">
                    <i class="fa-solid fa-file-excel"></i> Export Excel
                </button>
                <a href="/mis/list" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs px-4 py-2 rounded-lg transition-all border border-indigo-200">&#128203; MIS Centre</a>
            </div>
        </div>

        <!-- Filters Bar -->
        <div class="bg-white border border-slate-200 rounded-xl p-4 mb-4 shadow-sm">
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 items-end">
                <div class="lg:col-span-2">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">&#128269; Search</label>
                    <input type="text" id="grnSearch" placeholder="Item name, code, vendor..." oninput="applyGRNFilters()"
                        class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">From Date</label>
                    <input type="date" id="grnFrom" oninput="applyGRNFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">To Date</label>
                    <input type="date" id="grnTo" oninput="applyGRNFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Item Code</label>
                    <input type="text" id="grnCode" placeholder="Filter code..." oninput="applyGRNFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Vendor</label>
                    <input type="text" id="grnVendor" placeholder="Filter vendor..." oninput="applyGRNFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Uploaded By</label>
                    <input type="text" id="grnUploader" placeholder="Filter user..." oninput="applyGRNFilters()" class="filter-input">
                </div>
            </div>
            <div class="flex items-center justify-between mt-2.5">
                <span id="grnCount" class="text-[11px] text-slate-400 font-mono">Showing all records</span>
                <div class="flex items-center gap-3">
                    <button onclick="applyGRNFilters()" class="bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1"><i class="fa-solid fa-filter"></i> Apply Filters</button>
                    <button onclick="clearGRNFilters()" class="text-[10px] text-rose-500 font-bold hover:underline">Clear Filters</button>
                </div>
            </div>
        </div>

        <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
            <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse" id="grnTable">
                <thead>
                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase text-[10px] border-b border-slate-200">
                        <th class="p-3 whitespace-nowrap">Timestamp</th>
                        <th class="p-3">Item Name</th>
                        <th class="p-3">Item Code</th>
                        <th class="p-3 text-center">Qty / UOM</th>
                        <th class="p-3">Vendor</th>
                        <th class="p-3 text-center">GRN No.</th>
                        <th class="p-3 text-center">Challan No.</th>
                        <th class="p-3">Uploaded By</th>
                        <th class="p-3 text-right pr-4">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100" id="grnTbody">{rows if rows else '<tr><td colspan="9" class="p-8 text-center text-slate-400 text-sm">No GRNs uploaded yet.</td></tr>'}</tbody>
            </table>
            </div>
            <!-- Pagination -->
            <div class="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
                <span class="text-[11px] text-slate-400" id="grnPageInfo"></span>
                <div class="flex items-center gap-1" id="grnPagination"></div>
            </div>
        </div>
    </div>

<script>
var GRN_PAGE = 1, GRN_PER_PAGE = 20, GRN_FILTERED = null;
function getAllGRNRows() {{ return Array.from(document.querySelectorAll('#grnTbody .grn-row')); }}
function applyGRNFilters() {{
    var q = (document.getElementById('grnSearch').value||'').toLowerCase().trim();
    var from = document.getElementById('grnFrom').value;
    var to = document.getElementById('grnTo').value;
    var code = (document.getElementById('grnCode').value||'').toLowerCase().trim();
    var vendor = (document.getElementById('grnVendor').value||'').toLowerCase().trim();
    var uploader = (document.getElementById('grnUploader').value||'').toLowerCase().trim();
    GRN_FILTERED = getAllGRNRows().filter(function(r) {{
        var d = r.dataset.date||'';
        if(from && d < from) return false;
        if(to && d > to) return false;
        if(q && !r.dataset.item.includes(q) && !r.dataset.code.includes(q) && !r.dataset.vendor.includes(q) && !r.dataset.grn.includes(q)) return false;
        if(code && !r.dataset.code.includes(code)) return false;
        if(vendor && !r.dataset.vendor.includes(vendor)) return false;
        if(uploader && !r.dataset.uploader.includes(uploader)) return false;
        return true;
    }});
    GRN_PAGE = 1;
    renderGRNPage();
}}
function renderGRNPage() {{
    var rows = GRN_FILTERED !== null ? GRN_FILTERED : getAllGRNRows();
    var total = rows.length;
    var pages = Math.ceil(total / GRN_PER_PAGE) || 1;
    if(GRN_PAGE > pages) GRN_PAGE = pages;
    var start = (GRN_PAGE-1)*GRN_PER_PAGE, end = start+GRN_PER_PAGE;
    getAllGRNRows().forEach(function(r){{r.style.display='none';}});
    rows.slice(start,end).forEach(function(r){{r.style.display='';}});
    document.getElementById('grnCount').textContent = 'Showing ' + Math.min(start+1,total) + '–' + Math.min(end,total) + ' of ' + total + ' records';
    document.getElementById('grnPageInfo').textContent = 'Page ' + GRN_PAGE + ' of ' + pages;
    var pgDiv = document.getElementById('grnPagination');
    pgDiv.innerHTML = '';
    if(pages <= 1) return;
    var mkBtn = function(label,pg,active) {{
        var b = document.createElement('button');
        b.textContent = label;
        b.className = 'px-2.5 py-1 rounded text-[11px] font-bold border ' + (active ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50');
        b.onclick = function(){{ GRN_PAGE=pg; renderGRNPage(); }};
        return b;
    }};
    pgDiv.appendChild(mkBtn('«',1,false));
    pgDiv.appendChild(mkBtn('‹',Math.max(1,GRN_PAGE-1),false));
    for(var p=Math.max(1,GRN_PAGE-2);p<=Math.min(pages,GRN_PAGE+2);p++) pgDiv.appendChild(mkBtn(p,p,p===GRN_PAGE));
    pgDiv.appendChild(mkBtn('›',Math.min(pages,GRN_PAGE+1),false));
    pgDiv.appendChild(mkBtn('»',pages,false));
}}
function clearGRNFilters() {{
    ['grnSearch','grnFrom','grnTo','grnCode','grnVendor','grnUploader'].forEach(function(id){{document.getElementById(id).value='';}});
    GRN_FILTERED=null; GRN_PAGE=1; renderGRNPage();
}}
function exportGRN() {{
    var from = document.getElementById('grnFrom').value;
    var to = document.getElementById('grnTo').value;
    var rows = GRN_FILTERED !== null ? GRN_FILTERED : getAllGRNRows();
    var data = [['Timestamp','Item Name','Item Code','Qty','UOM','Vendor','GRN No.','Challan No.','Uploaded By']];
    rows.forEach(function(r) {{
        var cells = r.querySelectorAll('td');
        data.push([
            cells[0].textContent.trim(), cells[1].textContent.trim(), cells[2].textContent.trim(),
            cells[3].textContent.trim().split(' ')[0], cells[3].textContent.trim().split(' ')[1]||'',
            cells[4].textContent.trim(), cells[5].textContent.trim(), cells[6].textContent.trim(), cells[7].textContent.trim()
        ]);
    }});
    var ws = XLSX.utils.aoa_to_sheet(data);
    ws['!cols'] = [{{wch:18}},{{wch:28}},{{wch:14}},{{wch:8}},{{wch:8}},{{wch:22}},{{wch:14}},{{wch:14}},{{wch:14}}];
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'GRN Records');
    var fname = 'EIPL_GRN_Export' + (from?'_from_'+from:'') + (to?'_to_'+to:'') + '.xlsx';
    XLSX.writeFile(wb, fname);
}}
window.onload = function() {{ renderGRNPage(); }};
</script>
</div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/grn/download/{grn_id}")
def grn_download(grn_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import os
    from fastapi.responses import FileResponse, Response
    grn = db.query(models.GRNRecord).filter(models.GRNRecord.id == grn_id).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")

    # Preferred: bytes stored in the shared DB (works on every device)
    if getattr(grn, "grn_filedata", None):
        return Response(
            content=grn.grn_filedata,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{grn.grn_filename}"'}
        )

    # Fallback: legacy records whose bytes only live on this machine's disk
    grn_path = os.path.join("grn_uploads", grn.grn_filename or "")
    if grn.grn_filename and os.path.exists(grn_path):
        return FileResponse(path=grn_path, filename=grn.grn_filename, media_type="application/octet-stream")

    raise HTTPException(status_code=404, detail="GRN file missing from server")


@app.get("/mis/list", response_class=HTMLResponse)
def mis_list(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    assignments = db.query(models.MaterialAssignment).filter(
        models.MaterialAssignment.mis_filename != None
    ).order_by(models.MaterialAssignment.timestamp.desc()).all()
    rows = ""
    for a in assignments:
        ts = fmt_ist(a.timestamp)
        ts_iso = fmt_ist(a.timestamp, "%Y-%m-%d")
        item_name = a.item.name if a.item else "Unknown Item"
        item_code = a.item.item_code if a.item else "—"
        dept = getattr(a, 'department', '—') or '—'
        issued_by = getattr(a, 'issued_by', '—') or '—'
        rows += f"""
        <tr class="border-b hover:bg-slate-50 text-xs mis-row"
            data-date="{ts_iso}" data-item="{item_name.lower()}" data-code="{item_code.lower()}"
            data-issued="{a.issued_to.lower() if a.issued_to else ''}" data-dept="{dept.lower()}" data-by="{issued_by.lower()}">
            <td class="p-3 text-slate-500 font-mono whitespace-nowrap">{ts}</td>
            <td class="p-3 font-semibold text-slate-800">{item_name}</td>
            <td class="p-3 font-mono text-slate-500">{item_code}</td>
            <td class="p-3 text-center font-mono font-bold text-slate-700">{a.quantity} {a.uom}</td>
            <td class="p-3 text-slate-700 font-medium">{a.issued_to}</td>
            <td class="p-3 text-slate-500">{dept}</td>
            <td class="p-3 text-slate-400 text-[11px]">{issued_by}</td>
            <td class="p-3 text-right">
                <a href="/mis/download/{a.id}" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all">&#11015; Download MIS</a>
            </td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>MIS Download Centre - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>body{{font-family:'Inter',sans-serif;}}.filter-input{{font-size:11px;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;width:100%;box-sizing:border-box;}}
.filter-input:focus{{outline:none;border-color:#6366f1;background:#fff;}}</style>
</head>
<body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user, current_page='mis')}
<div class="flex-1 min-h-screen overflow-x-hidden p-6">
    <div class="max-w-7xl mx-auto">
        <div class="flex items-center justify-between mb-5">
            <div>
                <a href="/" class="text-indigo-600 text-xs font-bold hover:underline">&#8592; Back to Dashboard</a>
                <h1 class="text-xl font-black text-slate-900 mt-1">&#128203; MIS Download Centre</h1>
                <p class="text-xs text-slate-400 mt-0.5">Material Issue Slips — uploaded issuance records</p>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="exportMIS()" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-4 py-2 rounded-lg transition-all flex items-center gap-1.5">
                    <i class="fa-solid fa-file-excel"></i> Export Excel
                </button>
                <a href="/grn/list" class="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs px-4 py-2 rounded-lg transition-all border border-slate-200">&#128196; GRN Centre</a>
            </div>
        </div>

        <!-- Filters Bar -->
        <div class="bg-white border border-slate-200 rounded-xl p-4 mb-4 shadow-sm">
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 items-end">
                <div class="lg:col-span-2">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">&#128269; Search</label>
                    <input type="text" id="misSearch" placeholder="Item name, code, issued to..." oninput="applyMISFilters()"
                        class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">From Date</label>
                    <input type="date" id="misFrom" oninput="applyMISFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">To Date</label>
                    <input type="date" id="misTo" oninput="applyMISFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Item Code</label>
                    <input type="text" id="misCode" placeholder="Filter code..." oninput="applyMISFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Issued To</label>
                    <input type="text" id="misIssued" placeholder="Filter employee..." oninput="applyMISFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Department</label>
                    <input type="text" id="misDept" placeholder="Filter dept..." oninput="applyMISFilters()" class="filter-input">
                </div>
            </div>
            <div class="flex items-center justify-between mt-2.5">
                <span id="misCount" class="text-[11px] text-slate-400 font-mono">Showing all records</span>
                <div class="flex items-center gap-3">
                    <button onclick="applyMISFilters()" class="bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1"><i class="fa-solid fa-filter"></i> Apply Filters</button>
                    <button onclick="clearMISFilters()" class="text-[10px] text-rose-500 font-bold hover:underline">Clear Filters</button>
                </div>
            </div>
        </div>

        <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
            <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse" id="misTable">
                <thead>
                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase text-[10px] border-b border-slate-200">
                        <th class="p-3 whitespace-nowrap">Timestamp</th>
                        <th class="p-3">Item Name</th>
                        <th class="p-3">Item Code</th>
                        <th class="p-3 text-center">Qty / UOM</th>
                        <th class="p-3">Issued To</th>
                        <th class="p-3">Department</th>
                        <th class="p-3">Issued By</th>
                        <th class="p-3 text-right pr-4">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100" id="misTbody">{rows if rows else '<tr><td colspan="8" class="p-8 text-center text-slate-400 text-sm">No MIS records uploaded yet.</td></tr>'}</tbody>
            </table>
            </div>
            <!-- Pagination -->
            <div class="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
                <span class="text-[11px] text-slate-400" id="misPageInfo"></span>
                <div class="flex items-center gap-1" id="misPagination"></div>
            </div>
        </div>
    </div>

<script>
var MIS_PAGE = 1, MIS_PER_PAGE = 20, MIS_FILTERED = null;
function getAllMISRows() {{ return Array.from(document.querySelectorAll('#misTbody .mis-row')); }}
function applyMISFilters() {{
    var q = (document.getElementById('misSearch').value||'').toLowerCase().trim();
    var from = document.getElementById('misFrom').value;
    var to = document.getElementById('misTo').value;
    var code = (document.getElementById('misCode').value||'').toLowerCase().trim();
    var issued = (document.getElementById('misIssued').value||'').toLowerCase().trim();
    var dept = (document.getElementById('misDept').value||'').toLowerCase().trim();
    MIS_FILTERED = getAllMISRows().filter(function(r) {{
        var d = r.dataset.date||'';
        if(from && d < from) return false;
        if(to && d > to) return false;
        if(q && !r.dataset.item.includes(q) && !r.dataset.code.includes(q) && !r.dataset.issued.includes(q)) return false;
        if(code && !r.dataset.code.includes(code)) return false;
        if(issued && !r.dataset.issued.includes(issued)) return false;
        if(dept && !r.dataset.dept.includes(dept)) return false;
        return true;
    }});
    MIS_PAGE = 1;
    renderMISPage();
}}
function renderMISPage() {{
    var rows = MIS_FILTERED !== null ? MIS_FILTERED : getAllMISRows();
    var total = rows.length;
    var pages = Math.ceil(total / MIS_PER_PAGE) || 1;
    if(MIS_PAGE > pages) MIS_PAGE = pages;
    var start = (MIS_PAGE-1)*MIS_PER_PAGE, end = start+MIS_PER_PAGE;
    getAllMISRows().forEach(function(r){{r.style.display='none';}});
    rows.slice(start,end).forEach(function(r){{r.style.display='';}});
    document.getElementById('misCount').textContent = 'Showing ' + Math.min(start+1,total) + '–' + Math.min(end,total) + ' of ' + total + ' records';
    document.getElementById('misPageInfo').textContent = 'Page ' + MIS_PAGE + ' of ' + pages;
    var pgDiv = document.getElementById('misPagination');
    pgDiv.innerHTML = '';
    if(pages <= 1) return;
    var mkBtn = function(label,pg,active) {{
        var b = document.createElement('button');
        b.textContent = label;
        b.className = 'px-2.5 py-1 rounded text-[11px] font-bold border ' + (active ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50');
        b.onclick = function(){{ MIS_PAGE=pg; renderMISPage(); }};
        return b;
    }};
    pgDiv.appendChild(mkBtn('«',1,false));
    pgDiv.appendChild(mkBtn('‹',Math.max(1,MIS_PAGE-1),false));
    for(var p=Math.max(1,MIS_PAGE-2);p<=Math.min(pages,MIS_PAGE+2);p++) pgDiv.appendChild(mkBtn(p,p,p===MIS_PAGE));
    pgDiv.appendChild(mkBtn('›',Math.min(pages,MIS_PAGE+1),false));
    pgDiv.appendChild(mkBtn('»',pages,false));
}}
function clearMISFilters() {{
    ['misSearch','misFrom','misTo','misCode','misIssued','misDept'].forEach(function(id){{document.getElementById(id).value='';}});
    MIS_FILTERED=null; MIS_PAGE=1; renderMISPage();
}}
function exportMIS() {{
    var from = document.getElementById('misFrom').value;
    var to = document.getElementById('misTo').value;
    var rows = MIS_FILTERED !== null ? MIS_FILTERED : getAllMISRows();
    var data = [['Timestamp','Item Name','Item Code','Qty','UOM','Issued To','Department','Issued By']];
    rows.forEach(function(r) {{
        var cells = r.querySelectorAll('td');
        var qtyuom = cells[3].textContent.trim().split(' ');
        data.push([
            cells[0].textContent.trim(), cells[1].textContent.trim(), cells[2].textContent.trim(),
            qtyuom[0]||'', qtyuom[1]||'',
            cells[4].textContent.trim(), cells[5].textContent.trim(), cells[6].textContent.trim()
        ]);
    }});
    var ws = XLSX.utils.aoa_to_sheet(data);
    ws['!cols'] = [{{wch:18}},{{wch:28}},{{wch:14}},{{wch:8}},{{wch:8}},{{wch:22}},{{wch:18}},{{wch:18}}];
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'MIS Records');
    var fname = 'EIPL_MIS_Export' + (from?'_from_'+from:'') + (to?'_to_'+to:'') + '.xlsx';
    XLSX.writeFile(wb, fname);
}}
window.onload = function() {{ renderMISPage(); }};
</script>
</div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/mis/download/{assignment_id}")
def mis_download(assignment_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import os
    from fastapi.responses import FileResponse, Response
    a = db.query(models.MaterialAssignment).filter(models.MaterialAssignment.id == assignment_id).first()
    if not a or not a.mis_filename:
        raise HTTPException(status_code=404, detail="MIS not found")

    # Preferred: bytes stored in the shared DB (works on every device)
    if getattr(a, "mis_filedata", None):
        return Response(
            content=a.mis_filedata,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{a.mis_filename}"'}
        )

    # Fallback: legacy records whose bytes only live on this machine's disk
    mis_path = os.path.join("mis_uploads", a.mis_filename)
    if os.path.exists(mis_path):
        return FileResponse(path=mis_path, filename=a.mis_filename, media_type="application/octet-stream")

    raise HTTPException(status_code=404, detail="MIS file missing from server")


@app.get("/rts/list", response_class=HTMLResponse)
def rts_list(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return-to-Store Slip Download Centre — same UI as the GRN Centre."""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    returns = db.query(models.MaterialAssignment).filter(
        models.MaterialAssignment.is_return == True,
        models.MaterialAssignment.return_filename != None
    ).order_by(models.MaterialAssignment.timestamp.desc()).all()
    rows = ""
    for a in returns:
        ts = fmt_ist(a.timestamp)
        ts_iso = fmt_ist(a.timestamp, "%Y-%m-%d")
        item_name = a.item.name if a.item else "Unknown Item"
        item_code = a.item.item_code if a.item else "—"
        returned_by = a.issued_to or "—"
        recorded_by = a.mis_uploader.username if a.mis_uploader else (a.issued_by or "System")
        dept = a.department or "—"
        rows += f"""
        <tr class="border-b hover:bg-slate-50 text-xs rts-row"
            data-date="{ts_iso}" data-item="{item_name.lower()}" data-code="{item_code.lower()}"
            data-returnedby="{returned_by.lower()}" data-uploader="{recorded_by.lower()}">
            <td class="p-3 text-slate-500 font-mono whitespace-nowrap">{ts}</td>
            <td class="p-3 font-semibold text-slate-800">{item_name}</td>
            <td class="p-3 font-mono text-slate-500">{item_code}</td>
            <td class="p-3 text-center font-mono font-bold text-slate-700">{a.quantity} {a.uom or ''}</td>
            <td class="p-3 text-slate-600">{returned_by}</td>
            <td class="p-3 text-slate-500">{dept}</td>
            <td class="p-3 text-slate-500">{recorded_by}</td>
            <td class="p-3 text-right">
                <a href="/rts/download/{a.id}" class="bg-amber-500 hover:bg-amber-600 text-white font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all">&#11015; Download</a>
            </td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>RTS Downloads - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<style>body{{font-family:'Inter',sans-serif;}}.filter-input{{font-size:11px;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc;width:100%;box-sizing:border-box;}}
.filter-input:focus{{outline:none;border-color:#f59e0b;background:#fff;}}</style>
</head>
<body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user, current_page='rts')}
<div class="flex-1 min-h-screen overflow-x-hidden p-6">
    <div class="max-w-7xl mx-auto">
        <div class="flex items-center justify-between mb-5">
            <div>
                <a href="/" class="text-amber-600 text-xs font-bold hover:underline">&#8592; Back to Dashboard</a>
                <h1 class="text-xl font-black text-slate-900 mt-1">&#128230; Return to Store Slip Download Centre</h1>
                <p class="text-xs text-slate-400 mt-0.5">Return-to-Store slips — uploaded material return records</p>
            </div>
            <div class="flex items-center gap-2">
                <button onclick="exportRTS()" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-4 py-2 rounded-lg transition-all flex items-center gap-1.5">
                    <i class="fa-solid fa-file-excel"></i> Export Excel
                </button>
                <a href="/grn/list" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs px-4 py-2 rounded-lg transition-all border border-indigo-200">&#128196; GRN Centre</a>
                <a href="/mis/list" class="bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold text-xs px-4 py-2 rounded-lg transition-all border border-rose-200">&#128203; MIS Centre</a>
            </div>
        </div>

        <!-- Filters Bar -->
        <div class="bg-white border border-slate-200 rounded-xl p-4 mb-4 shadow-sm">
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 items-end">
                <div class="lg:col-span-2">
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">&#128269; Search</label>
                    <input type="text" id="rtsSearch" placeholder="Item, code, employee..." oninput="applyRTSFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">From Date</label>
                    <input type="date" id="rtsFrom" oninput="applyRTSFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">To Date</label>
                    <input type="date" id="rtsTo" oninput="applyRTSFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Returned By</label>
                    <input type="text" id="rtsReturnedBy" placeholder="Filter employee..." oninput="applyRTSFilters()" class="filter-input">
                </div>
                <div>
                    <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Recorded By</label>
                    <input type="text" id="rtsUploader" placeholder="Filter user..." oninput="applyRTSFilters()" class="filter-input">
                </div>
            </div>
            <div class="flex items-center justify-between mt-2.5">
                <span id="rtsCount" class="text-[11px] text-slate-400 font-mono">Showing all records</span>
                <div class="flex items-center gap-3">
                    <button onclick="applyRTSFilters()" class="bg-amber-500 hover:bg-amber-600 text-white text-[10px] font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1"><i class="fa-solid fa-filter"></i> Apply Filters</button>
                    <button onclick="clearRTSFilters()" class="text-[10px] text-rose-500 font-bold hover:underline">Clear Filters</button>
                </div>
            </div>
        </div>

        <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
            <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse" id="rtsTable">
                <thead>
                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase text-[10px] border-b border-slate-200">
                        <th class="p-3 whitespace-nowrap">Timestamp</th>
                        <th class="p-3">Item Name</th>
                        <th class="p-3">Item Code</th>
                        <th class="p-3 text-center">Qty / UOM</th>
                        <th class="p-3">Returned By</th>
                        <th class="p-3">Department</th>
                        <th class="p-3">Recorded By</th>
                        <th class="p-3 text-right pr-4">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100" id="rtsTbody">{rows if rows else '<tr><td colspan="8" class="p-8 text-center text-slate-400 text-sm">No Return-to-Store slips uploaded yet.</td></tr>'}</tbody>
            </table>
            </div>
            <div class="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
                <span class="text-[11px] text-slate-400" id="rtsPageInfo"></span>
                <div class="flex items-center gap-1" id="rtsPagination"></div>
            </div>
        </div>
    </div>

<script>
var RTS_PAGE = 1, RTS_PER_PAGE = 20, RTS_FILTERED = null;
function getAllRTSRows() {{ return Array.from(document.querySelectorAll('#rtsTbody .rts-row')); }}
function applyRTSFilters() {{
    var q = (document.getElementById('rtsSearch').value||'').toLowerCase().trim();
    var from = document.getElementById('rtsFrom').value;
    var to = document.getElementById('rtsTo').value;
    var emp = (document.getElementById('rtsReturnedBy').value||'').toLowerCase().trim();
    var uploader = (document.getElementById('rtsUploader').value||'').toLowerCase().trim();
    RTS_FILTERED = getAllRTSRows().filter(function(r) {{
        var d = r.dataset.date||'';
        if(from && d < from) return false;
        if(to && d > to) return false;
        if(q && !r.dataset.item.includes(q) && !r.dataset.code.includes(q) && !r.dataset.returnedby.includes(q)) return false;
        if(emp && !r.dataset.returnedby.includes(emp)) return false;
        if(uploader && !r.dataset.uploader.includes(uploader)) return false;
        return true;
    }});
    RTS_PAGE = 1; renderRTSPage();
}}
function renderRTSPage() {{
    var rows = RTS_FILTERED !== null ? RTS_FILTERED : getAllRTSRows();
    var total = rows.length;
    var pages = Math.ceil(total / RTS_PER_PAGE) || 1;
    if(RTS_PAGE > pages) RTS_PAGE = pages;
    var start = (RTS_PAGE-1)*RTS_PER_PAGE, end = start+RTS_PER_PAGE;
    getAllRTSRows().forEach(function(r){{r.style.display='none';}});
    rows.slice(start,end).forEach(function(r){{r.style.display='';}});
    document.getElementById('rtsCount').textContent = 'Showing ' + Math.min(start+1,total) + '-' + Math.min(end,total) + ' of ' + total + ' records';
    document.getElementById('rtsPageInfo').textContent = 'Page ' + RTS_PAGE + ' of ' + pages;
    var pgDiv = document.getElementById('rtsPagination');
    pgDiv.innerHTML = '';
    if(pages <= 1) return;
    var mkBtn = function(label,pg,active) {{
        var b = document.createElement('button');
        b.textContent = label;
        b.className = 'px-2.5 py-1 rounded text-[11px] font-bold border ' + (active ? 'bg-amber-500 text-white border-amber-500' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50');
        b.onclick = function(){{ RTS_PAGE=pg; renderRTSPage(); }};
        return b;
    }};
    pgDiv.appendChild(mkBtn('\u00ab',1,false));
    pgDiv.appendChild(mkBtn('\u2039',Math.max(1,RTS_PAGE-1),false));
    for(var p=Math.max(1,RTS_PAGE-2);p<=Math.min(pages,RTS_PAGE+2);p++) pgDiv.appendChild(mkBtn(p,p,p===RTS_PAGE));
    pgDiv.appendChild(mkBtn('\u203a',Math.min(pages,RTS_PAGE+1),false));
    pgDiv.appendChild(mkBtn('\u00bb',pages,false));
}}
function clearRTSFilters() {{
    ['rtsSearch','rtsFrom','rtsTo','rtsReturnedBy','rtsUploader'].forEach(function(id){{document.getElementById(id).value='';}});
    RTS_FILTERED=null; RTS_PAGE=1; renderRTSPage();
}}
function exportRTS() {{
    var from = document.getElementById('rtsFrom').value;
    var to = document.getElementById('rtsTo').value;
    var rows = RTS_FILTERED !== null ? RTS_FILTERED : getAllRTSRows();
    var data = [['Timestamp','Item Name','Item Code','Qty','UOM','Returned By','Department','Recorded By']];
    rows.forEach(function(r) {{
        var cells = r.querySelectorAll('td');
        var qty = cells[3].textContent.trim().split(' ');
        data.push([
            cells[0].textContent.trim(), cells[1].textContent.trim(), cells[2].textContent.trim(),
            qty[0]||'', qty.slice(1).join(' ')||'',
            cells[4].textContent.trim(), cells[5].textContent.trim(), cells[6].textContent.trim()
        ]);
    }});
    var ws = XLSX.utils.aoa_to_sheet(data);
    ws['!cols'] = [{{wch:18}},{{wch:28}},{{wch:14}},{{wch:8}},{{wch:8}},{{wch:22}},{{wch:18}},{{wch:18}}];
    var wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'RTS Records');
    var fname = 'EIPL_RTS_Export' + (from?'_from_'+from:'') + (to?'_to_'+to:'') + '.xlsx';
    XLSX.writeFile(wb, fname);
}}
window.onload = function() {{ renderRTSPage(); }};
</script>
</div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/rts/download/{assignment_id}")
def rts_download(assignment_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import os
    from fastapi.responses import FileResponse, Response
    a = db.query(models.MaterialAssignment).filter(models.MaterialAssignment.id == assignment_id).first()
    if not a or not a.return_filename:
        raise HTTPException(status_code=404, detail="Return-to-Store slip not found")

    # Preferred: bytes from shared DB
    if getattr(a, "return_filedata", None):
        return Response(
            content=a.return_filedata,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{a.return_filename}"'}
        )

    # Fallback: bytes on local disk
    rts_path = os.path.join("rts_uploads", a.return_filename)
    if os.path.exists(rts_path):
        return FileResponse(path=rts_path, filename=a.return_filename, media_type="application/octet-stream")

    raise HTTPException(status_code=404, detail="Return-to-Store slip file missing from server")


@app.post("/items/bulk-import")
async def items_bulk_import(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Access Denied", status_code=403)

    try:
        contents = await file.read()
        if not contents:
            return HTMLResponse("<script>alert('Error: Uploaded file is empty.'); window.location='/';</script>")
            
        try:
            decoded_content = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                decoded_content = contents.decode('cp1252')
            except UnicodeDecodeError:
                decoded_content = contents.decode('latin-1')

        clean_lines = decoded_content.splitlines()
        
        try:
            sample_data = "\n".join(clean_lines[:5])
            dialect = csv.Sniffer().sniff(sample_data)
            if dialect.delimiter not in [',', ';', '\t', '|']:
                dialect.delimiter = ','
            reader = csv.DictReader(clean_lines, dialect=dialect)
        except Exception:
            reader = csv.DictReader(clean_lines)

        added_count = 0
        updated_count = 0
        row_index = 0

        for row in reader:
            row_index += 1
            if not row:
                continue
                
            clean_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k is not None}

            name = clean_row.get("name") or clean_row.get("item name") or clean_row.get("item_name") or clean_row.get("product name")
            item_code = clean_row.get("item_code") or clean_row.get("code") or clean_row.get("item code") or clean_row.get("sku")

            if not name or not item_code:
                continue

            item_code = item_code.upper()

            try:
                stock_raw = clean_row.get("initial_stock") or clean_row.get("stock") or clean_row.get("current_stock") or clean_row.get("quantity") or "0"
                initial_stock = int(float(stock_raw))

                price_raw = clean_row.get("price") or clean_row.get("rate") or "0.0"
                price = float(price_raw)
            except ValueError:
                continue

            vendor = clean_row.get("vendor") or clean_row.get("supplier") or ""
            site = clean_row.get("site") or clean_row.get("storage_site") or ""

            exists = db.query(models.Item).filter(models.Item.item_code == item_code).first()
            if exists:
                exists.name = name
                exists.current_stock = initial_stock
                exists.price = price
                if hasattr(exists, 'supplier'): exists.supplier = vendor
                if hasattr(exists, 'storage_site'): exists.storage_site = site
                updated_count += 1
            else:
                new_item = models.Item(
                    name=name,
                    item_code=item_code,
                    current_stock=initial_stock,
                    price=price,
                    minimum_stock=5
                )
                if hasattr(new_item, 'supplier'): new_item.supplier = vendor
                if hasattr(new_item, 'storage_site'): new_item.storage_site = site
                
                db.add(new_item)
                added_count += 1

        db.commit()
        return HTMLResponse(f"<script>alert('Bulk Process Complete! Added: {added_count}, Updated: {updated_count}'); window.location='/';</script>")
        
    except Exception as e:
        db.rollback()
        print(f"[Bulk Import Critical Exception]: {str(e)}")
        return HTMLResponse(f"<script>alert('Import processing error: {str(e)}'); window.location='/';</script>")


@app.get("/items/bulk-template")
def items_bulk_template(current_user: models.User = Depends(get_current_user)):
    if not current_user or current_user.role != "Admin":
        return RedirectResponse(url="/login", status_code=303)
    from fastapi.responses import StreamingResponse
    import io
    csv_content = "name,item_code,initial_stock,price,vendor,site\n"
    csv_content += "Steel Pipe 25mm,EIPL-ST-01,50,350.00,Tata Steel,Udaipur Yard\n"
    csv_content += "Copper Cable 4mm,EIPL-CC-02,100,125.50,Polycab,Store Room A\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=EIPL_Items_Bulk_Template.csv"}
    )


@app.post("/items/add")
def add_item(
    name: str = Form(...),
    item_code: str = Form(...),
    price: float = Form(0.0),
    initial_stock: int = Form(0),
    minimum_stock: int = Form(0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    existing_item = db.query(models.Item).filter(models.Item.item_code == item_code).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="Item code already exists!")

    db_item = models.Item(
        name=name,
        item_code=item_code,
        price=price,
        current_stock=initial_stock,
        minimum_stock=minimum_stock
    )
    db.add(db_item)
    db.flush()

    if initial_stock > 0:
        item_unit_price = price if price is not None else 0.0
        initial_transaction = models.Transaction(
            item_id=db_item.id,
            type="IN",
            quantity=initial_stock,
            user_id=current_user.id,
            total_value=float(initial_stock * item_unit_price)
        )
        db.add(initial_transaction)

    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/items/edit/{item_id}")
def edit_item(
    item_id: int,
    name: str = Form(...),
    item_code: str = Form(...),
    current_stock: int = Form(...),
    minimum_stock: int = Form(...),
    price: float = Form(...),
    supplier: str = Form(""),
    storage_site: str = Form(""),
    category: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        return HTMLResponse("<html><body><h2>Access Denied: Admin privileges required</h2></body></html>", status_code=403)
        
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Check if the new item_code is already used by a DIFFERENT item
    duplicate = db.query(models.Item).filter(
        models.Item.item_code == item_code.strip().upper(),
        models.Item.id != item_id
    ).first()
    if duplicate:
        return HTMLResponse(
            f"<script>alert('Error: Item code \"{item_code.upper()}\" is already assigned to another item. Please use a unique code.'); window.history.back();</script>"
        )

    db_item.name = name
    db_item.item_code = item_code.strip().upper()
    stock_delta = current_stock - (db_item.current_stock or 0)
    db_item.minimum_stock = minimum_stock
    db_item.price = price
    if supplier.strip():
        db_item.supplier = supplier.strip()
    if storage_site.strip():
        db_item.storage_site = storage_site.strip()
    if category and category.strip() in ASSET_CLASSES:
        db_item.category = category.strip()
    # current_stock is updated by reconcile_stock_delta via the lot ledger
    reconcile_stock_delta(db, db_item, stock_delta)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/items/delete/{item_id}")
def delete_item(item_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Access Denied", status_code=403)
    db.query(models.ItemLot).filter(models.ItemLot.item_id == item_id).delete()
    db.query(models.Transaction).filter(models.Transaction.item_id == item_id).delete()
    db.query(models.ProcurementRequest).filter(models.ProcurementRequest.item_id == item_id).delete()
    db.query(models.MaterialAssignment).filter(models.MaterialAssignment.item_id == item_id).delete()
    db.query(models.Item).filter(models.Item.id == item_id).delete()
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/items/update-stock-direct/{item_id}")
def update_stock_direct(
    item_id: int,
    new_stock: int = Form(...),
    session_user: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item:
        delta = int(new_stock) - (item.current_stock or 0)
        reconcile_stock_delta(db, item, delta)
        db.commit()
        
    return RedirectResponse(url="/", status_code=303)


@app.post("/material/issue")
async def issue_materials(
    item_id: int = Form(...),
    quantity: int = Form(...),
    uom: str = Form(...),
    issued_to: str = Form(...),
    issued_by: str = Form(None),
    department: str = Form("General Operations"),
    remarks: str = Form(None),
    asset_unit_id: int = Form(None),     # required when issuing a Fixed Asset / Equipment unit
    mis_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    if not issued_by:
        issued_by = current_user.full_name or current_user.username

    if not mis_file or not mis_file.filename:
        return HTMLResponse("<script>alert('MIS (Material Issue Slip) upload is mandatory before recording an issue.'); window.history.back();</script>")

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        return RedirectResponse(url="/?error=item_not_found", status_code=303)

    tracked = is_tracked(item)
    asset_unit = None
    if tracked:
        if not asset_unit_id:
            return HTMLResponse("<script>alert('Select a specific serial number to issue this Fixed Asset / Equipment.'); window.history.back();</script>")
        asset_unit = db.query(models.AssetUnit).filter(
            models.AssetUnit.id == asset_unit_id,
            models.AssetUnit.item_id == item_id
        ).first()
        if not asset_unit:
            return HTMLResponse("<script>alert('Selected asset unit not found.'); window.history.back();</script>")
        if asset_unit.status != "In Stock":
            return HTMLResponse(f"<script>alert('Serial {asset_unit.serial_no} is currently {asset_unit.status}, not In Stock. Refresh and re-select.'); window.history.back();</script>")
        quantity = 1
    else:
        if (item.current_stock or 0) < quantity:
            return RedirectResponse(url="/?error=insufficient_stock", status_code=303)

    import os, datetime as dt
    mis_dir = "mis_uploads"
    os.makedirs(mis_dir, exist_ok=True)
    timestamp_str = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"MIS_{item.item_code}_{timestamp_str}_{mis_file.filename.replace(' ', '_')}"
    mis_path = os.path.join(mis_dir, safe_filename)
    contents = await mis_file.read()
    with open(mis_path, "wb") as f:
        f.write(contents)

    if tracked:
        fifo_cost = float(item.price or 0.0)
        item.current_stock = (item.current_stock or 0) - 1
    else:
        fifo_cost = consume_fifo(db, item, quantity)

    now = dt.datetime.utcnow()
    new_assignment = models.MaterialAssignment(
        item_id=item_id,
        quantity=quantity,
        uom=uom,
        issued_to=issued_to,
        issued_by=issued_by,
        department=department,
        remarks=remarks,
        custodian=issued_to,
        mis_filename=safe_filename,
        mis_filedata=contents,
        mis_uploaded_by_id=current_user.id,
        mis_upload_timestamp=now,
        timestamp=now,
        asset_unit_id=(asset_unit.id if tracked else None),
    )
    db.add(new_assignment)
    db.flush()

    if tracked:
        asset_unit.status = "Issued"
        asset_unit.current_holder = issued_to
        asset_unit.current_assignment_id = new_assignment.id

    db.add(models.Transaction(
        item_id=item_id,
        type="OUT",
        quantity=quantity,
        total_value=fifo_cost,
        user_id=current_user.id,
        timestamp=now
    ))

    db.commit()
    return RedirectResponse(url="/?tab=allocations", status_code=303)


@app.post("/material/return")
async def return_to_store(
    item_id: int = Form(...),
    quantity: int = Form(...),
    returned_by: str = Form(...),               # the employee returning the material
    department: str = Form("General Operations"),
    remarks: str = Form(None),
    asset_unit_id: int = Form(None),            # for tracked items: which serial is coming back
    return_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Record a return-to-store. For consumables/tools this adds quantity back via a
    return lot; for Fixed Assets and Equipments it flips the specific AssetUnit
    back to In Stock."""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    if not return_file or not return_file.filename:
        return HTMLResponse("<script>alert('Return-to-Store Slip is mandatory before recording a return.'); window.history.back();</script>")

    if quantity <= 0:
        return HTMLResponse("<script>alert('Return quantity must be greater than zero.'); window.history.back();</script>")

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        return HTMLResponse("<script>alert('Item not found.'); window.history.back();</script>")

    tracked = is_tracked(item)
    asset_unit = None

    if tracked:
        if not asset_unit_id:
            return HTMLResponse("<script>alert('Select the specific serial number being returned.'); window.history.back();</script>")
        asset_unit = db.query(models.AssetUnit).filter(
            models.AssetUnit.id == asset_unit_id,
            models.AssetUnit.item_id == item_id
        ).first()
        if not asset_unit:
            return HTMLResponse("<script>alert('Selected asset unit not found.'); window.history.back();</script>")
        if asset_unit.status != "Issued" or asset_unit.current_holder != returned_by:
            return HTMLResponse(f"<script>alert('Serial {asset_unit.serial_no} is not currently held by {returned_by}.'); window.history.back();</script>")
        quantity = 1
    else:
        # Net issued to this employee = sum issues - sum prior returns
        issued_total = db.query(models.MaterialAssignment).filter(
            models.MaterialAssignment.item_id == item_id,
            models.MaterialAssignment.issued_to == returned_by,
            (models.MaterialAssignment.is_return == False) | (models.MaterialAssignment.is_return.is_(None))
        ).all()
        returned_total = db.query(models.MaterialAssignment).filter(
            models.MaterialAssignment.item_id == item_id,
            models.MaterialAssignment.issued_to == returned_by,
            models.MaterialAssignment.is_return == True
        ).all()
        net_held = sum(a.quantity or 0 for a in issued_total) - sum(a.quantity or 0 for a in returned_total)
        if quantity > net_held:
            return HTMLResponse(f"<script>alert('Cannot return {quantity} units. {returned_by} currently holds only {net_held}.'); window.history.back();</script>")

    import os, datetime as dt
    rts_dir = "rts_uploads"
    os.makedirs(rts_dir, exist_ok=True)
    timestamp_str = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"RTS_{item.item_code}_{timestamp_str}_{return_file.filename.replace(' ', '_')}"
    rts_path = os.path.join(rts_dir, safe_filename)
    contents = await return_file.read()
    with open(rts_path, "wb") as f:
        f.write(contents)

    if tracked:
        asset_unit.status = "In Stock"
        asset_unit.current_holder = None
        asset_unit.current_assignment_id = None
        item.current_stock = (item.current_stock or 0) + 1
    else:
        return_vendor = f"Returned by {returned_by}"
        add_to_lot(db, item, return_vendor, 0.0, quantity)

    now = dt.datetime.utcnow()
    db.add(models.MaterialAssignment(
        item_id=item_id,
        quantity=quantity,
        uom=item.uom or "Nos",
        issued_to=returned_by,
        issued_by=current_user.full_name or current_user.username,
        department=department,
        remarks=remarks,
        custodian=returned_by,
        is_return=True,
        return_filename=safe_filename,
        return_filedata=contents,
        mis_uploaded_by_id=current_user.id,
        mis_upload_timestamp=now,
        timestamp=now,
        asset_unit_id=(asset_unit.id if tracked else None),
    ))

    db.add(models.Transaction(
        item_id=item_id,
        type="RETURN",
        quantity=quantity,
        total_value=0.0,
        user_id=current_user.id,
        timestamp=now
    ))

    db.commit()
    return RedirectResponse(url="/?tab=allocations", status_code=303)
@app.post("/procurement/request")
def create_procurement_request(
    item_id: str = Form(...),
    quantity: int = Form(...),
    department: str = Form(...),
    new_item_name: str = Form(None),
    detailed_specification: str = Form(None),
    category: str = Form(None),
    db: Session = Depends(get_db),
    user_str: str = Cookie(None, alias="session_user")
):
    if not user_str:
        return RedirectResponse(url="/login", status_code=303)
    
    current_user = db.query(models.User).filter(models.User.username == user_str).first()

    clean_category = category.strip() if category and category.strip() in ASSET_CLASSES else DEFAULT_ASSET_CLASS

    new_request = models.ProcurementRequest(
        quantity=quantity,
        department=department.strip(),
        requested_by_id=current_user.id,
        status="Pending",
        category=clean_category
    )

    if item_id == "NEW_PROCUREMENT_AD_HOC":
        new_request.is_new_item = True
        new_request.item_id = None
        new_request.new_item_name = new_item_name.strip() if new_item_name else "Unlisted Item"
        new_request.detailed_specification = detailed_specification.strip() if detailed_specification else "No specs"
        new_request.total_estimated_cost = 0.0
    else:
        item_ent = db.query(models.Item).filter(models.Item.id == int(item_id)).first()
        if not item_ent:
            return HTMLResponse("<h2>Error: Item not found in Catalog</h2>", status_code=400)
        
        new_request.is_new_item = False
        new_request.item_id = item_ent.id
        new_request.total_estimated_cost = float(item_ent.price * quantity)
        # Keep the catalog item's category in sync with the indent's chosen category
        item_ent.category = clean_category
        new_request.category = item_ent.category

    db.add(new_request)
    db.commit()
    return RedirectResponse(url="/#requisitions-panel", status_code=303)


@app.post("/procurement/assign-code/{req_id}")
def assign_item_code(
    req_id: int,
    new_item_code: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)

    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if not req:
        return HTMLResponse("<script>alert('Request not found.'); window.history.back();</script>")

    clean_code = new_item_code.strip().upper()

    # Check uniqueness against existing catalog items
    duplicate = db.query(models.Item).filter(models.Item.item_code == clean_code).first()
    if duplicate:
        return HTMLResponse(
            f"<script>alert('Error: Code \"{clean_code}\" already exists in catalog for \"{duplicate.name}\". Please use a unique code.'); window.history.back();</script>"
        )

    # Store assigned code in the supplier field of the pending request (reuse unused nullable field)
    # We prefix it clearly so Accept logic can detect and extract it
    req.new_item_name = f"[CODE:{clean_code}]{req.new_item_name.split(']', 1)[-1] if ']' in (req.new_item_name or '') else (req.new_item_name or '')}"
    db.commit()
    return RedirectResponse(url="/#requisitions-panel", status_code=303)



@app.post("/procurement/assign-spec/{req_id}")
def assign_specification(
    req_id: int,
    specification: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if not req:
        return HTMLResponse("<script>alert('Request not found.'); window.history.back();</script>")

    clean_spec = specification.strip()
    if not clean_spec:
        return HTMLResponse("<script>alert('Specification cannot be empty.'); window.history.back();</script>")

    req.detailed_specification = clean_spec
    db.commit()
    return RedirectResponse(url="/#requisitions-panel", status_code=303)



@app.post("/procurement/message/{req_id}")
def post_procurement_message(
    req_id: int,
    message: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if not req:
        return HTMLResponse("<script>alert('Request not found.'); window.history.back();</script>")
    msg = models.ProcurementMessage(
        request_id=req_id,
        sender_id=current_user.id,
        message=message.strip()
    )
    db.add(msg)
    db.commit()
    return RedirectResponse(url="/#requisitions-panel", status_code=303)


@app.get("/procurement/bulk-template")
def procurement_bulk_template(current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    from fastapi.responses import StreamingResponse
    import io
    csv_content = "item_id_or_NEW,item_name,specification,quantity,department\n"
    csv_content += "1,,(leave blank for existing items),5,Operations\n"
    csv_content += "NEW,Steel Pipe 25mm,Grade A - 25mm dia x 6m length - IS 1239,10,Mechanical\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=EIPL_Procurement_Indent_Template.csv"}
    )


@app.post("/procurement/bulk-import")
async def procurement_bulk_import(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    try:
        contents = await file.read()
        try:
            decoded = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = contents.decode('latin-1')
        lines = decoded.splitlines()
        reader = csv.DictReader(lines)
        added = 0
        for row in reader:
            clean = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k}
            item_ref = clean.get("item_id_or_new", "").upper()
            quantity_raw = clean.get("quantity", "1")
            department = clean.get("department", "General Operations")
            try:
                quantity = int(float(quantity_raw))
            except ValueError:
                continue
            if quantity < 1:
                continue
            new_req = models.ProcurementRequest(
                quantity=quantity,
                department=department.strip(),
                requested_by_id=current_user.id,
                status="Pending",
                total_estimated_cost=0.0
            )
            if item_ref == "NEW":
                new_req.is_new_item = True
                new_req.item_id = None
                new_req.new_item_name = clean.get("item_name", "Unlisted Item").strip() or "Unlisted Item"
                new_req.detailed_specification = clean.get("specification", "No specs").strip() or "No specs"
            else:
                try:
                    item_id = int(item_ref)
                    item_ent = db.query(models.Item).filter(models.Item.id == item_id).first()
                    if not item_ent:
                        continue
                    new_req.is_new_item = False
                    new_req.item_id = item_ent.id
                    new_req.total_estimated_cost = float(item_ent.price * quantity)
                except ValueError:
                    continue
            db.add(new_req)
            added += 1
        db.commit()
        return HTMLResponse(f"<script>alert('Bulk Import Complete! {added} indent(s) created.'); window.location='/#requisitions-panel';</script>")
    except Exception as e:
        db.rollback()
        return HTMLResponse(f"<script>alert('Import error: {str(e)}'); window.history.back();</script>")


@app.get("/procurement/export-excel")
def procurement_export_excel(
    date_from: str = None,
    date_to: str = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export procurement pipeline to Excel with optional date range filter."""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import io, datetime as _dt
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return HTMLResponse("<script>alert('openpyxl not installed on server.'); window.history.back();</script>")

    reqs = db.query(models.ProcurementRequest).order_by(models.ProcurementRequest.timestamp.desc()).all()

    # Apply date filter
    if date_from:
        try:
            dt_from = _dt.datetime.strptime(date_from, "%Y-%m-%d")
            reqs = [r for r in reqs if r.timestamp and r.timestamp >= dt_from]
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = _dt.datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            reqs = [r for r in reqs if r.timestamp and r.timestamp <= dt_to]
        except ValueError:
            pass

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Procurement Pipeline"

    # Header styling
    hdr_fill = PatternFill("solid", fgColor="1E293B")
    hdr_font = Font(bold=True, color="FFFFFF", size=10)
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = ["#", "Date", "Item Name", "Item Code", "Qty", "Est. Value (₹)", "Vendor", "Unit Rate (₹)", "Department", "Requested By", "Status", "Specification"]
    col_widths = [4, 16, 30, 16, 8, 14, 22, 14, 18, 14, 14, 40]

    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.row_dimensions[1].height = 24

    # Status colors
    status_fills = {
        "Pending": PatternFill("solid", fgColor="FEF9C3"),
        "Order Pending": PatternFill("solid", fgColor="DBEAFE"),
        "Order Placed": PatternFill("solid", fgColor="E0E7FF"),
        "Delivered": PatternFill("solid", fgColor="D1FAE5"),
        "Rejected": PatternFill("solid", fgColor="FEE2E2"),
    }

    for ri, r in enumerate(reqs, 2):
        date_str = fmt_ist(r.timestamp)
        if getattr(r, 'is_new_item', False):
            raw_name = r.new_item_name or ""
            if raw_name.startswith("[CODE:"):
                item_code_str = raw_name[len("[CODE:"):raw_name.index("]")]
                item_name_str = raw_name[raw_name.index("]") + 1:].strip() or "New Item"
            else:
                item_name_str = raw_name or "Unlisted Item"
                item_code_str = "—"
        else:
            item_name_str = r.item.name if r.item else (r.new_item_name or "—")
            item_code_str = r.item.item_code if r.item else "—"

        row_data = [
            ri - 1,
            date_str,
            item_name_str,
            item_code_str,
            r.quantity or 0,
            round(r.total_estimated_cost or 0.0, 2),
            r.vendor or "—",
            round(r.unit_price or 0.0, 2) if r.unit_price else "—",
            r.department or "—",
            r.requester.username if r.requester else "—",
            r.status or "—",
            r.detailed_specification or "—"
        ]
        sfill = status_fills.get(r.status)
        for ci, val in enumerate(row_data, 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.alignment = Alignment(horizontal="center" if ci in [1,4,5,6,8] else "left", vertical="center", wrap_text=(ci == 12))
            if sfill:
                cell.fill = sfill
        ws.row_dimensions[ri].height = 15

    # Freeze header row
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    suffix = ""
    if date_from: suffix += f"_from_{date_from}"
    if date_to: suffix += f"_to_{date_to}"
    filename = f"EIPL_Procurement_Pipeline{suffix}.xlsx"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/admin/verify-password")
def admin_verify_password(
    password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns JSON 200 if admin password is correct, 403 otherwise."""
    from fastapi.responses import JSONResponse
    if not current_user or current_user.role != "Admin":
        return JSONResponse({"ok": False, "msg": "Not an admin account."}, status_code=403)
    if current_user.hashed_password != hash_password(password):
        return JSONResponse({"ok": False, "msg": "Incorrect admin password."}, status_code=403)
    return JSONResponse({"ok": True})


@app.post("/procurement/set-pricing/{req_id}")
def set_procurement_pricing(
    req_id: int,
    vendor: str = Form(...),
    unit_price: float = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Only the admin may enter vendor + rate, and only before the order is placed
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if req and req.status == "Order Pending":
        v = (vendor or "").strip()
        if not v or unit_price is None or unit_price < 0:
            return HTMLResponse("<script>alert('Enter a valid vendor and rate.'); window.history.back();</script>")
        req.vendor = v
        req.unit_price = float(unit_price)
        req.total_estimated_cost = float((req.quantity or 0) * float(unit_price))
        # Mirror onto the catalog item so it shows as the latest known vendor/price
        if req.item:
            req.item.supplier = v
            req.item.price = float(unit_price)
        db.commit()
    return RedirectResponse(url="/?tab=requisitions", status_code=303)


@app.post("/procurement/order/{req_id}")
def place_order(req_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if req and req.status == "Order Pending":
        # The order can only be placed once the admin has entered vendor + rate
        if not (req.vendor and req.vendor.strip()) or req.unit_price is None:
            return HTMLResponse("<script>alert('Enter vendor and rate before placing the order.'); window.history.back();</script>")
        req.status = "Order Placed"
        db.commit()
    return RedirectResponse(url="/?tab=requisitions", status_code=303)


@app.post("/procurement/action/{req_id}/{action_token}")
def handle_procurement_action(
    req_id: int,
    action_token: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)

    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if req:
        if action_token.lower() == "accept":
            # Block Accept for new items that haven't had a code assigned yet
            if getattr(req, 'is_new_item', False) and req.item_id is None:
                raw_name = req.new_item_name or ""
                if not raw_name.startswith("[CODE:"):
                    return HTMLResponse(
                        "<script>alert('Cannot approve: Please assign a unique Item Code to this new item request before approving.'); window.history.back();</script>"
                    )
                # Check specification is filled
                raw_spec = req.detailed_specification or ""
                if not raw_spec.strip() or raw_spec.strip().lower() == "no specs":
                    return HTMLResponse(
                        "<script>alert('Cannot approve: Please add the item specification before approving.'); window.history.back();</script>"
                    )
                # Extract the assigned code and the real item name
                code_part = raw_name[len("[CODE:"):raw_name.index("]")]
                real_name = raw_name[raw_name.index("]") + 1:].strip() or "New Procured Item"
                assigned_code = code_part.strip().upper()
            
            req.status = "Order Pending"

            # For new ad-hoc items: create catalog entry with 0 stock (delivered via inward later)
            if getattr(req, 'is_new_item', False) and req.item_id is None:
                new_catalog_item = models.Item(
                    item_code=assigned_code,
                    name=real_name,
                    description=req.detailed_specification,
                    category=(req.category if getattr(req, 'category', None) in ASSET_CLASSES else DEFAULT_ASSET_CLASS),
                    supplier="Pending Selection",
                    storage_site=req.department,
                    price=0.0,
                    current_stock=0,
                    minimum_stock=0
                )
                db.add(new_catalog_item)
                db.flush()
                req.item_id = new_catalog_item.id
            # Stock NOT added here — added when inward transaction is recorded
        else:
            req.status = "Rejected"
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/procurement/edit/{request_id}")
def edit_procurement_request(
    request_id: int,
    item_id: int = Form(...),
    quantity: int = Form(...),
    department: str = Form(...),
    session_user: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)
        
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/", status_code=303)
        
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item:
        req.item_id = item_id
        req.quantity = quantity
        req.total_estimated_cost = float(quantity * item.price)
        req.department = department
        db.commit()
        
    return RedirectResponse(url="/", status_code=303)


@app.post("/procurement/delete/{request_id}")
def delete_procurement_request(
    request_id: int,
    session_user: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)
    # Admin-only: non-admins cannot delete procurement requests
    user = db.query(models.User).filter(models.User.username == session_user).first()
    if not user or user.role != "Admin":
        return HTMLResponse("Access Denied: Admin privileges required to delete records.", status_code=403)
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == request_id).first()
    if req:
        db.delete(req)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/admin/users/create")
def admin_create_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    designation: str = Form(...),
    workstation_location: str = Form(...),
    role: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)

    if db.query(models.User).filter(models.User.username == username.strip().lower()).first():
        return HTMLResponse("<script>alert('Conflict: Identifier taken.'); window.location='/';</script>")

    db.add(models.User(
        username=username.strip().lower(),
        hashed_password=hash_password(password.strip()),
        role=role.strip(),
        full_name=full_name.strip(),
        designation=designation.strip(),
        workstation_location=workstation_location.strip()
    ))
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/admin/users/edit/{target_id}")
def admin_edit_user(
    target_id: int,
    full_name: str = Form(...),
    designation: str = Form(...),
    workstation_location: str = Form(...),
    role: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)

    user = db.query(models.User).filter(models.User.id == target_id).first()
    if user:
        user.full_name = full_name.strip()
        user.designation = designation.strip()
        user.workstation_location = workstation_location.strip()
        user.role = role.strip()
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/account/password", response_class=HTMLResponse)
def account_password_page(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import html as _html

    admin_reset_panel = ""
    if current_user.role == "Admin":
        staff_users = db.query(models.User).filter(models.User.role != "Admin").order_by(models.User.username).all()
        rows = ""
        for u in staff_users:
            rows += f"""
            <div class="flex items-center justify-between bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] mb-1.5">
                <div>
                    <p class="font-bold text-slate-800">{_html.escape(u.username)} ({_html.escape(u.role)})</p>
                    <p class="text-slate-500 text-[10px]">{_html.escape(u.full_name or '')}</p>
                </div>
                <button type="button" onclick="toggleResetForm({u.id})" class="text-indigo-600 font-bold hover:underline text-[10px]">set password</button>
            </div>
            <form id="resetForm{u.id}" action="/admin/users/set-password/{u.id}" method="POST" class="hidden mb-3 p-2.5 bg-indigo-50/50 border border-indigo-100 rounded-lg space-y-2">
                <input type="password" name="new_password" placeholder="New password for {_html.escape(u.username)}" required minlength="4"
                    class="w-full bg-white border border-slate-200 p-2 rounded-lg text-xs">
                <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-2 rounded-lg font-bold text-xs">Update Password</button>
            </form>"""
        admin_reset_panel = f"""
        <div class="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 mt-6">
            <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase border-b border-slate-100 pb-3 mb-3">&#128272; Reset Staff Password</h2>
            <p class="text-[10px] text-slate-400 mb-3">As Admin, you can set a new password for any Staff account. Admin accounts cannot reset each other's passwords here.</p>
            {rows if rows else '<p class="text-[11px] text-slate-400">No staff accounts found.</p>'}
        </div>
        <script>
        function toggleResetForm(id) {{
            var f = document.getElementById('resetForm' + id);
            f.classList.toggle('hidden');
        }}
        </script>
        """

    html_page = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>Change Password - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{{font-family:'Inter',sans-serif;}}</style>
</head><body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user, current_page='password')}
<div class="flex-1 flex flex-col min-h-screen overflow-x-hidden">
<div class="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-8 shrink-0 shadow-sm z-10">
    <div class="flex items-center gap-2 text-xs font-semibold text-slate-400">
        <span class="uppercase tracking-wider text-indigo-600 font-bold">EIPL Framework</span>
        <i class="fa-solid fa-chevron-right text-[9px] text-slate-300"></i>
        <span class="text-slate-700 font-medium">Change Password</span>
    </div>
    <span class="text-[11px] text-slate-400 font-mono">{_html.escape(current_user.username)} ({current_user.role})</span>
</div>
<div class="max-w-xl w-full mx-auto p-6">
    <div class="bg-white border border-slate-200 rounded-2xl shadow-sm p-5">
        <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase border-b border-slate-100 pb-3 mb-3">&#128273; Change My Password</h2>
        <form action="/account/change-password" method="POST" class="space-y-3 text-xs text-slate-700">
            <div><label class="block font-semibold text-slate-500 mb-1">Current Password</label>
                <input type="password" name="current_password" required class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-xs"></div>
            <div><label class="block font-semibold text-slate-500 mb-1">New Password</label>
                <input type="password" name="new_password" required minlength="4" class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-xs"></div>
            <div><label class="block font-semibold text-slate-500 mb-1">Confirm New Password</label>
                <input type="password" name="confirm_password" required minlength="4" class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-xs"></div>
            <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all text-xs">Update Password</button>
        </form>
        <div class="mt-3 pt-3 border-t border-slate-100">
            <p class="text-[10px] text-slate-400 leading-relaxed">
                <i class="fa-solid fa-circle-info text-slate-400 mr-1"></i>
                <b>Forgot your current password?</b> Ask your EIPL administrator to issue a temporary password
                from the Grant User Access panel; you can then sign in and change it from here.
            </p>
        </div>
    </div>
    {admin_reset_panel}
</div>
</div>
</body></html>"""
    return HTMLResponse(html_page)


@app.post("/account/change-password")
def account_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    if current_user.hashed_password != hash_password(current_password):
        return HTMLResponse("<script>alert('Current password is incorrect.'); window.history.back();</script>")
    if new_password != confirm_password:
        return HTMLResponse("<script>alert('New password and confirmation do not match.'); window.history.back();</script>")
    if len(new_password) < 4:
        return HTMLResponse("<script>alert('New password must be at least 4 characters.'); window.history.back();</script>")
    current_user.hashed_password = hash_password(new_password)
    db.commit()
    return HTMLResponse("<script>alert('Password updated successfully.'); window.location='/account/password';</script>")


@app.post("/admin/users/set-password/{target_id}")
def admin_set_user_password(
    target_id: int,
    new_password: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)
    target = db.query(models.User).filter(models.User.id == target_id).first()
    if not target:
        return HTMLResponse("<script>alert('User not found.'); window.location='/account/password';</script>")
    if target.role == "Admin":
        return HTMLResponse("<script>alert('Admins cannot reset another admin\\'s password.'); window.location='/account/password';</script>")
    if len(new_password) < 4:
        return HTMLResponse("<script>alert('New password must be at least 4 characters.'); window.history.back();</script>")
    target.hashed_password = hash_password(new_password)
    db.commit()
    return HTMLResponse(f"<script>alert('Password updated for {target.username}.'); window.location='/account/password';</script>")


@app.post("/admin/users/delete/{target_id}")
def admin_delete_user(target_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)
    if current_user.id == target_id:
        return HTMLResponse("<script>alert('Constraint blocked.'); window.location='/';</script>")

    db.query(models.User).filter(models.User.id == target_id).delete()
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/employees/add")
def add_employee(
    name: str = Form(...),
    role_title: str = Form(...),
    location: str = Form("Not Specified"),
    contact: str = Form("Not Specified"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Access Denied", status_code=403)

    db.add(models.Employee(
        name=name.strip(),
        role_title=role_title.strip(),
        location=location.strip(),
        contact=contact.strip()
    ))
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/employees/edit/{emp_id}")
def edit_employee(
    emp_id: int,
    name: str = Form(...),
    role_title: str = Form(...),
    location: str = Form(...),
    contact: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Access Denied", status_code=403)

    emp = db.query(models.Employee).filter(models.Employee.id == emp_id).first()
    if emp:
        emp.name = name.strip()
        emp.role_title = role_title.strip()
        emp.location = location.strip()
        emp.contact = contact.strip()
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/employees/delete/{emp_id}")
def delete_employee(emp_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Access Denied", status_code=403)

    db.query(models.Employee).filter(models.Employee.id == emp_id).delete()
    db.commit()
    return RedirectResponse(url="/", status_code=303)


def build_sidebar(current_user, current_page: str = "") -> str:
    """Returns the persistent left sidebar HTML for standalone pages.
    `current_page` keys: material-movement, grn, mis, rts, password."""
    import html as _html
    role_initial = (current_user.role or "S")[0].upper()
    # Style helpers for active vs inactive nav items
    nav_active = "w-full flex items-center gap-3 px-3 py-2.5 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-xl text-sm font-bold transition-all text-left"
    nav_idle   = "w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all group"
    sub_active = "w-full flex items-center gap-3 px-3 py-2 text-indigo-700 bg-indigo-50 border border-indigo-100/50 rounded-lg text-xs font-bold transition-all"
    sub_idle   = "w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-all group"
    def cls(key, active_cls, idle_cls):
        return active_cls if current_page == key else idle_cls
    def icon_cls(key, active_color, idle_size="w-5"):
        # active variant uses solid color, idle uses muted slate with hover tint
        if current_page == key:
            return f"fa-solid {idle_size} text-center {active_color}"
        return f"fa-solid {idle_size} text-center text-slate-400 group-hover:{active_color}"
    return f"""
    <aside class="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0 shadow-sm z-20 sticky top-0 h-screen">
        <div class="p-5 border-b border-slate-100 text-center">
            <img src="/static/logo.png" alt="EIPL Logo" class="h-16 mx-auto mb-2 object-contain"
                onerror="this.style.display='none';document.getElementById('sbLogoFallback').style.display='inline-block';">
            <div id="sbLogoFallback" style="display:none;" class="bg-indigo-600 px-3 py-2 rounded-xl text-white font-black text-sm mb-2">EIPL</div>
            <h2 class="font-black text-slate-900 tracking-tight text-[13px] leading-tight uppercase">Electra Infracon Pvt Ltd</h2>
            <p class="text-[10px] text-slate-400 font-mono mt-1">{_html.escape(current_user.username)}</p>
        </div>
        <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2">Core Dashboard</p>
            <a href="/?tab=requisitions" class="{nav_idle}">
                <i class="fa-solid fa-file-invoice-dollar w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Requisitions
            </a>
            <a href="/material-movement" class="{cls('material-movement', nav_active, nav_idle)}">
                <i class="{icon_cls('material-movement', 'text-emerald-600')} fa-truck-ramp-box"></i> Material Movement
            </a>
            <a href="/" class="{nav_idle}">
                <i class="fa-solid fa-boxes-stacked w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Inventory Configuration Log
            </a>
            <a href="/?tab=allocations" class="{nav_idle}">
                <i class="fa-solid fa-list-check w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Allocation Log
            </a>
            <div class="pt-4 mt-4 border-t border-slate-100 space-y-1">
                <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2">Administration</p>
                <a href="/?open=employee" class="{sub_idle}">
                    <i class="fa-solid fa-user-plus w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> Employee Registry
                </a>
                <a href="/?open=access" class="{sub_idle}">
                    <i class="fa-solid fa-key w-4 text-center text-slate-400 group-hover:text-emerald-600"></i> Grant User Access
                </a>
                <a href="/grn/list" class="{cls('grn', sub_active, sub_idle)}">
                    <i class="{icon_cls('grn', 'text-indigo-600', 'w-4')} fa-download"></i> GRN Download Centre
                </a>
                <a href="/mis/list" class="{cls('mis', sub_active, sub_idle)}">
                    <i class="{icon_cls('mis', 'text-indigo-600', 'w-4')} fa-file-arrow-down"></i> MIS Download Centre
                </a>
                <a href="/rts/list" class="{cls('rts', sub_active, sub_idle)}">
                    <i class="{icon_cls('rts', 'text-amber-600', 'w-4')} fa-arrow-rotate-left"></i> RTS Download Centre
                </a>
                <a href="/account/password" class="{cls('password', sub_active, sub_idle)}">
                    <i class="{icon_cls('password', 'text-indigo-600', 'w-4')} fa-lock"></i> Change Password
                </a>
            </div>
        </nav>
        <div class="p-4 border-t border-slate-100 bg-slate-50/50">
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2.5 min-w-0">
                    <div class="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center font-bold text-[11px] text-indigo-700 shrink-0">{role_initial}</div>
                    <div class="min-w-0">
                        <h4 class="text-xs font-bold text-slate-900 leading-none truncate">{_html.escape(current_user.full_name or current_user.username)}</h4>
                        <span class="text-[10px] text-slate-400 mt-0.5 inline-block truncate max-w-[120px]">{_html.escape(current_user.designation or '')}</span>
                    </div>
                </div>
                <a href="/logout" class="text-slate-400 hover:text-rose-600 transition-colors p-1.5 rounded-lg hover:bg-rose-50" title="Sign Out">
                    <i class="fa-solid fa-right-from-bracket text-xs"></i>
                </a>
            </div>
        </div>
    </aside>"""



@app.get("/rts/bulk-template")
def rts_bulk_template(current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    from fastapi.responses import StreamingResponse
    import io
    csv_content = "item_code,quantity,uom,returned_by,department,remarks\n"
    csv_content += "EIPL-ST-01,2,Nos,Piyush Bhatia,Udaipur Project,Unused — returned to store\n"
    csv_content += "EIPL-CC-02,5,Mtr,Biswajit Pradhan,Electrical Works,Excess cable returned\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=EIPL_RTS_Bulk_Template.csv"}
    )


@app.get("/mis/bulk-template")
def mis_bulk_template(current_user: models.User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    from fastapi.responses import StreamingResponse
    import io
    csv_content = "item_code,quantity,uom,issued_to,department,remarks\n"
    csv_content += "EIPL-ST-01,10,Nos,Piyush Bhatia,Udaipur Project,For site installation\n"
    csv_content += "EIPL-CC-02,50,Mtr,Biswajit Pradhan,Electrical Works,Cable run phase 2\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=EIPL_MIS_Bulk_Template.csv"}
    )


@app.post("/mis/bulk-import")
async def mis_bulk_import(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    try:
        contents = await file.read()
        try:
            decoded = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            decoded = contents.decode('latin-1')
        lines = [l for l in decoded.splitlines() if l.strip() and not l.strip().startswith('#')]
        reader = csv.DictReader(lines)
        added = 0
        errors = []
        import datetime as _dt
        for row in reader:
            clean = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k}
            item_code = clean.get("item_code", "").upper()
            quantity_raw = clean.get("quantity", "0")
            uom = clean.get("uom", "Nos")
            issued_to = clean.get("issued_to", "").strip()
            department = clean.get("department", "General Operations").strip()
            remarks = clean.get("remarks", "").strip()

            if not item_code or not issued_to:
                errors.append(f"Skipped row — missing item_code or issued_to")
                continue
            try:
                quantity = int(float(quantity_raw))
            except ValueError:
                errors.append(f"Skipped {item_code} — invalid quantity")
                continue
            if quantity < 1:
                errors.append(f"Skipped {item_code} — quantity must be >= 1")
                continue

            item = db.query(models.Item).filter(models.Item.item_code == item_code).first()
            if not item:
                errors.append(f"Skipped {item_code} — item not found in catalog")
                continue
            if item.current_stock < quantity:
                errors.append(f"Skipped {item_code} — insufficient stock ({item.current_stock} available)")
                continue

            bulk_fifo_cost = consume_fifo(db, item, quantity)
            now_ts = _dt.datetime.utcnow()
            db.add(models.MaterialAssignment(
                item_id=item.id,
                quantity=quantity,
                uom=uom or (item.uom or "Nos"),
                issued_to=issued_to,
                issued_by=current_user.full_name or current_user.username,
                department=department,
                remarks=remarks,
                custodian=issued_to,
                timestamp=now_ts
            ))
            # Record outward transaction for the flow dashboard
            db.add(models.Transaction(
                item_id=item.id,
                type="OUT",
                quantity=quantity,
                total_value=bulk_fifo_cost,
                user_id=current_user.id,
                timestamp=now_ts
            ))
            added += 1

        db.commit()
        msg = f"MIS Bulk Import: {added} issue(s) recorded."
        if errors:
            msg += " Errors: " + " | ".join(errors[:5])
        return HTMLResponse(f"<script>alert('{msg}'); window.location='/material-movement';</script>")
    except Exception as e:
        db.rollback()
        return HTMLResponse(f"<script>alert('MIS Bulk Import Error: {str(e)}'); window.history.back();</script>")


@app.get("/material-movement", response_class=HTMLResponse)
def material_movement_page(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    items = db.query(models.Item).order_by(models.Item.name).all()
    employees = db.query(models.Employee).order_by(models.Employee.name).all()
    import json as _json, html as _html
    inv_json = _json.dumps([{
        "id": i.id, "name": i.name, "code": i.item_code, "stock": i.current_stock,
        "uom": getattr(i,'uom',None) or "", "price": i.price or 0.0,
        "vendor": getattr(i,'supplier','') or "",
        "category": getattr(i, 'category', None) or DEFAULT_ASSET_CLASS,
        "tracked": is_tracked(i),
    } for i in items])

    item_by_id = {i.id: i for i in items}

    # Tracked items: in-stock asset units for the Outward serial picker
    in_stock_units = {}
    for u in db.query(models.AssetUnit).filter(models.AssetUnit.status == "In Stock").all():
        in_stock_units.setdefault(u.item_id, []).append({"id": u.id, "serial_no": u.serial_no})
    units_by_item_json = _json.dumps(in_stock_units)

    # Held units per employee (tracked items only) — for Return picker
    held_units_map = {}
    for u in db.query(models.AssetUnit).filter(models.AssetUnit.status == "Issued").all():
        if not u.current_holder:
            continue
        it = item_by_id.get(u.item_id)
        if not it:
            continue
        held_units_map.setdefault(u.current_holder, []).append({
            "asset_unit_id": u.id, "serial_no": u.serial_no,
            "item_id": u.item_id, "item_name": it.name, "item_code": it.item_code,
            "uom": (it.uom or "Nos"),
            "category": getattr(it, 'category', None) or DEFAULT_ASSET_CLASS,
        })
    held_units_json = _json.dumps(held_units_map)

    # Consumable/tools net-held per (employee, item) — skip tracked items (handled above)
    held = {}
    all_assigns = db.query(models.MaterialAssignment).all()
    for a in all_assigns:
        if not a.issued_to or not a.item_id:
            continue
        it = item_by_id.get(a.item_id)
        if it and is_tracked(it):
            continue
        key = (a.issued_to, a.item_id)
        sign = -1 if getattr(a, "is_return", False) else +1
        held[key] = held.get(key, 0) + sign * (a.quantity or 0)
    held_map = {}
    for (emp, iid), qty in held.items():
        if qty <= 0:
            continue
        it = item_by_id.get(iid)
        if not it:
            continue
        held_map.setdefault(emp, []).append({
            "item_id": iid, "name": it.name, "code": it.item_code,
            "uom": (it.uom or "Nos"), "qty_held": qty,
            "category": getattr(it, 'category', None) or DEFAULT_ASSET_CLASS,
        })
    held_json = _json.dumps(held_map)

    emp_opts = "".join([f'<option value="{_html.escape(e.name)}">{_html.escape(e.name)} ({e.role_title})</option>' for e in employees])
    recv = _html.escape(current_user.full_name or current_user.username)
    html_page = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>Material Movement - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{{font-family:'Inter',sans-serif;}}</style>
</head><body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user, current_page='material-movement')}
<div class="flex-1 flex flex-col min-h-screen overflow-x-hidden">
<div class="bg-white border-b border-slate-200 h-16 flex items-center justify-between px-8 shrink-0 shadow-sm z-10">
    <div class="flex items-center gap-2 text-xs font-semibold text-slate-400">
        <span class="uppercase tracking-wider text-indigo-600 font-bold">EIPL Framework</span>
        <i class="fa-solid fa-chevron-right text-[9px] text-slate-300"></i>
        <span class="text-slate-700 font-medium">Material Movement</span>
    </div>
    <span class="text-[11px] text-slate-400 font-mono">{_html.escape(current_user.username)} ({current_user.role})</span>
</div>
<div class="max-w-[1600px] mx-auto p-6">
  <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">

  <!-- LEFT: INWARD -->
  <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
    <div class="flex items-center justify-between px-5 py-3 border-b-2 border-emerald-400 bg-emerald-50/60">
      <div>
        <div class="flex items-center gap-2 mb-0.5">
          <span class="bg-emerald-500 text-white text-[10px] font-black px-2 py-0.5 rounded tracking-widest uppercase">Inward</span>
          <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase">&#8595; Material Inward</h2>
        </div>
        <p class="text-[10px] text-slate-400">Search existing item or register new — GRN mandatory</p>
      </div>
      <a href="/inward/bulk-template" class="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 px-2 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 whitespace-nowrap"><i class="fa-solid fa-download"></i> Template</a>
    </div>
    <form action="/transaction" method="POST" enctype="multipart/form-data" class="p-5 space-y-3 text-xs text-slate-700">
      <div>
        <label class="block font-semibold text-slate-600 mb-1">Search &amp; Select Item</label>
        <div class="relative">
          <input type="text" id="inward_item_search" placeholder="Type item name or code..." autocomplete="off"
            class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-emerald-500 focus:bg-white shadow-sm text-xs"
            oninput="filterInwardItems(this.value)" onfocus="showInwardDropdown()">
          <div id="inward_item_dropdown" class="absolute z-30 w-full bg-white border border-slate-200 rounded-xl shadow-xl mt-1 max-h-48 overflow-y-auto hidden"></div>
        </div>
        <input type="hidden" id="inward_item_id" name="item_id" value="" required>
        <p id="inward_selected_label" class="text-[10px] text-slate-400 mt-1 italic">No item selected</p>
      </div>
      <div>
        <label class="block font-semibold text-slate-500 mb-1">Category</label>
        <input type="text" id="inward_category_display" readonly placeholder="\u2014 (auto-filled)"
          class="w-full bg-slate-100 border border-slate-200 p-2 rounded-lg text-xs text-slate-500 cursor-not-allowed">
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div><label class="block font-semibold text-slate-500 mb-1">Quantity Received</label>
          <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg font-mono font-semibold text-xs"></div>
        <div><label class="block font-semibold text-slate-500 mb-1">Unit of Measure</label>
          <select id="inward_uom_select" name="uom" required class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs focus:outline-none focus:border-indigo-500">
            <option value="Nos">Nos</option><option value="Mtr">Mtr</option><option value="Kg">Kg</option>
            <option value="Ltr">Ltr</option><option value="Set">Set</option><option value="Pair">Pair</option>
            <option value="Box">Box</option><option value="Roll">Roll</option><option value="Bag">Bag</option>
            <option value="Ton">Ton</option><option value="Sqm">Sqm</option><option value="Rmt">Rmt</option><option value="Lot">Lot</option>
          </select></div>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div><label class="block font-semibold text-slate-500 mb-1">GRN No.</label>
          <input type="text" name="grn_no" placeholder="e.g. GRN-2026-001" class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs focus:outline-none focus:border-emerald-500"></div>
        <div><label class="block font-semibold text-slate-500 mb-1">Challan / Invoice No.</label>
          <input type="text" name="challan_no" placeholder="e.g. INV-4521" class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs focus:outline-none focus:border-emerald-500"></div>
      </div>
      <div class="bg-indigo-50/60 border border-indigo-100 rounded-lg p-2 text-[11px] text-indigo-700 font-medium">
        <i class="fa-solid fa-user-check mr-1"></i> Received By: <span class="font-black">{recv} ({_html.escape(current_user.username)})</span>
      </div>
      <div id="inward_serial_block" class="hidden bg-amber-50/40 border border-amber-200/60 rounded-xl p-3">
        <div class="flex items-center justify-between mb-1">
          <label class="block font-bold text-amber-700 text-[10px] uppercase tracking-wider">
            <i class="fa-solid fa-barcode mr-1"></i> Serial Numbers <span class="text-rose-500">*</span>
          </label>
          <button type="button" onclick="autoFillSerials()" class="text-[10px] text-amber-700 hover:underline font-bold">Auto-fill</button>
        </div>
        <textarea id="inward_serial_numbers" name="serial_numbers" rows="3" placeholder="EIPL-LAP-001&#10;EIPL-LAP-002&#10;..."
          class="w-full bg-white border border-amber-200 p-2 rounded-lg font-mono text-[11px] focus:outline-none focus:border-amber-500"></textarea>
        <p class="text-[10px] text-amber-700 mt-1 leading-snug">
          One serial per line. Required because this item is a <b>Fixed Asset / Equipment</b>.
          The number of serials must match the Quantity Received.
        </p>
      </div>
      <div><label class="block font-semibold text-slate-500 mb-1">Upload GRN <span class="text-rose-500 font-black">*</span></label>
        <input type="file" name="grn_file" required accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx"
          class="w-full bg-rose-50 border border-rose-200 text-slate-700 text-[10px] p-2 rounded-lg">
        <p class="text-[10px] text-rose-500 mt-0.5">&#9888; GRN must be uploaded to proceed</p>
      </div>
      <button type="submit" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all text-xs">&#10003; Record Inward &amp; Upload GRN</button>
    </form>
    <div class="px-5 pb-5 border-t border-dashed border-slate-200 pt-3">
      <label class="block font-black text-[10px] uppercase text-emerald-700 mb-2">&#128202; Bulk Inward Import (CSV)</label>
      <form action="/inward/bulk-import" method="POST" enctype="multipart/form-data" class="flex gap-2">
        <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border border-slate-200 text-slate-600 text-[10px] p-2 rounded-xl">
        <button type="submit" class="bg-emerald-600 text-white px-3 py-2 rounded-xl font-bold text-[10px] shrink-0">Import</button>
      </form>
    </div>
  </div>

  <!-- RIGHT: OUTWARD -->
  <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
    <div class="px-5 py-3 border-b-2 border-rose-400 bg-rose-50/60">
      <div class="flex items-center justify-between mb-0.5">
        <div class="flex items-center gap-2">
          <span class="bg-rose-500 text-white text-[10px] font-black px-2 py-0.5 rounded tracking-widest uppercase">Outward</span>
          <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase">&#8593; Material Issue</h2>
        </div>
        <a href="/mis/bulk-template" class="bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-300 px-2 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 whitespace-nowrap"><i class="fa-solid fa-download"></i> Template</a>
      </div>
      <p class="text-[10px] text-slate-400">Issue materials from store — MIS upload mandatory</p>
    </div>
    <form action="/material/issue" method="POST" enctype="multipart/form-data" class="p-5 space-y-3 text-xs text-slate-700">
      <div>
        <label class="block font-semibold text-slate-600 mb-1">Search &amp; Select Item</label>
        <div class="relative">
          <input type="text" id="mis_item_search" placeholder="Type item name or code..." autocomplete="off"
            class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-rose-500 focus:bg-white shadow-sm text-xs"
            oninput="filterMISItems(this.value)" onfocus="showMISDropdown()">
          <div id="mis_item_dropdown" class="absolute z-30 w-full bg-white border border-slate-200 rounded-xl shadow-xl mt-1 max-h-48 overflow-y-auto hidden"></div>
        </div>
        <input type="hidden" id="mis_item_id" name="item_id" required>
        <p id="mis_selected_label" class="text-[10px] text-slate-400 mt-1 italic">No item selected</p>
      </div>
      <div>
        <label class="block font-semibold text-slate-500 mb-1">Category</label>
        <input type="text" id="mis_category_display" readonly placeholder="\u2014 (auto-filled)"
          class="w-full bg-slate-100 border border-slate-200 p-2 rounded-lg text-xs text-slate-500 cursor-not-allowed">
      </div>
      <div id="mis_serial_block" class="hidden bg-amber-50/40 border border-amber-200/60 rounded-xl p-3">
        <label class="block font-bold text-amber-700 text-[10px] uppercase tracking-wider mb-1">
          <i class="fa-solid fa-barcode mr-1"></i> Select Serial <span class="text-rose-500">*</span>
        </label>
        <select id="mis_asset_unit" name="asset_unit_id" class="w-full bg-white border border-amber-200 p-2 rounded-lg font-mono text-[11px] focus:outline-none focus:border-amber-500">
          <option value="">-- Select serial in stock --</option>
        </select>
        <p class="text-[10px] text-amber-700 mt-1">One physical unit per issue (Fixed Asset / Equipment).</p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div><label class="block font-semibold text-slate-500 mb-1">Quantity to Issue</label>
          <input type="number" name="quantity" min="1" value="1" required class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg font-mono font-semibold text-xs"></div>
        <div><label class="block font-semibold text-slate-500 mb-1">UOM</label>
          <input type="text" id="mis_uom_display" name="uom" placeholder="UOM (auto-filled)" readonly class="w-full bg-indigo-50 border border-indigo-200 p-2 rounded-lg text-xs font-bold text-indigo-700"></div>
      </div>
      <div><label class="block font-semibold text-slate-500 mb-1">Issue To (Employee)</label>
        <select name="issued_to" required class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl text-xs focus:outline-none focus:border-indigo-500">
          <option value="">&#8212; Select Employee &#8212;</option>{emp_opts}
        </select></div>
      <div><label class="block font-semibold text-slate-500 mb-1">Department</label>
        <input type="text" name="department" placeholder="e.g. Udaipur Project" class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs"></div>
      <div><label class="block font-semibold text-slate-500 mb-1">Remarks (optional)</label>
        <input type="text" name="remarks" placeholder="Purpose / Location" class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs"></div>
      <div><label class="block font-semibold text-slate-500 mb-1">Upload MIS <span class="text-rose-500 font-black">*</span></label>
        <input type="file" name="mis_file" required accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx"
          class="w-full bg-rose-50 border border-rose-200 text-slate-700 text-[10px] p-2 rounded-lg"></div>
      <button type="submit" class="w-full bg-rose-600 hover:bg-rose-700 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all text-xs">&#8593; Issue Material &amp; Upload MIS</button>
    </form>
    <div class="px-5 pb-5 border-t border-dashed border-slate-200 pt-3">
      <label class="block font-black text-[10px] uppercase text-rose-700 tracking-wider mb-2">&#128202; Bulk MIS Import (CSV)</label>
      <form action="/mis/bulk-import" method="POST" enctype="multipart/form-data" class="flex gap-2">
        <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border border-slate-200 text-slate-600 text-[10px] p-2 rounded-xl">
        <button type="submit" class="bg-rose-600 text-white px-3 py-2 rounded-xl font-bold text-[10px] shrink-0">Import</button>
      </form>
      <p class="text-[10px] text-slate-400 mt-1">Columns: item_code, quantity, uom, issued_to, department, remarks</p>
    </div>
  </div>

  <!-- RIGHTMOST: RETURN TO STORE -->
  <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
    <div class="px-5 py-3 border-b-2 border-amber-400 bg-amber-50/60">
      <div class="flex items-center justify-between mb-0.5">
        <div class="flex items-center gap-2">
          <span class="bg-amber-500 text-white text-[10px] font-black px-2 py-0.5 rounded tracking-widest uppercase">Return</span>
          <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase">&#8634; Return to Store</h2>
        </div>
        <a href="/rts/bulk-template" class="bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-300 px-2 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 whitespace-nowrap"><i class="fa-solid fa-download"></i> Template</a>
      </div>
      <p class="text-[10px] text-slate-400">Take returned materials back into stock &mdash; slip mandatory</p>
    </div>
    <form action="/material/return" method="POST" enctype="multipart/form-data" class="p-5 space-y-3 text-xs text-slate-700">
      <div>
        <label class="block font-semibold text-slate-600 mb-1">Returning Employee</label>
        <select id="rts_employee" name="returned_by" required onchange="onRtsEmployeeChange()"
          class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl focus:outline-none focus:border-amber-500 focus:bg-white text-xs">
          <option value="">-- Select Employee --</option>
          {emp_opts}
        </select>
      </div>

      <div id="rts_held_panel" class="hidden bg-amber-50/40 border border-amber-200/60 rounded-xl p-3">
        <p class="text-[10px] font-bold text-amber-700 uppercase tracking-wider mb-1.5">Items currently held by this employee</p>
        <div id="rts_held_list" class="space-y-1 text-[11px] text-slate-700 max-h-32 overflow-y-auto"></div>
      </div>
      <div id="rts_no_items" class="hidden bg-slate-50 border border-slate-200 rounded-xl p-3 text-center">
        <p class="text-[11px] text-slate-500">No outstanding items for this employee.</p>
      </div>

      <div>
        <label class="block font-semibold text-slate-600 mb-1">Item Being Returned</label>
        <select id="rts_item" name="item_id" required disabled onchange="onRtsItemChange()"
          class="w-full bg-slate-50 border border-slate-200 p-2.5 rounded-xl focus:outline-none focus:border-amber-500 focus:bg-white text-xs disabled:opacity-50">
          <option value="">-- Select employee first --</option>
        </select>
      </div>

      <div id="rts_serial_block" class="hidden bg-amber-50/40 border border-amber-200/60 rounded-xl p-3">
        <label class="block font-bold text-amber-700 text-[10px] uppercase tracking-wider mb-1">
          <i class="fa-solid fa-barcode mr-1"></i> Serial Being Returned <span class="text-rose-500">*</span>
        </label>
        <select id="rts_asset_unit" name="asset_unit_id" class="w-full bg-white border border-amber-200 p-2 rounded-lg font-mono text-[11px] focus:outline-none focus:border-amber-500">
          <option value="">-- Select serial being returned --</option>
        </select>
        <p class="text-[10px] text-amber-700 mt-1">One physical unit per return (Fixed Asset / Equipment).</p>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block font-semibold text-slate-500 mb-1">Quantity Returned</label>
          <input type="number" id="rts_qty" name="quantity" min="1" value="1" required
            class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg font-mono font-semibold text-xs">
          <p id="rts_qty_help" class="text-[10px] text-slate-400 mt-0.5">Max: \u2014</p>
        </div>
        <div>
          <label class="block font-semibold text-slate-500 mb-1">UOM (auto)</label>
          <input type="text" id="rts_uom_display" readonly placeholder="\u2014"
            class="w-full bg-slate-100 border border-slate-200 p-2 rounded-lg text-xs text-slate-500 cursor-not-allowed">
        </div>
      </div>

      <div>
        <label class="block font-semibold text-slate-500 mb-1">Category</label>
        <input type="text" id="rts_category_display" readonly placeholder="\u2014 (auto-filled)"
          class="w-full bg-slate-100 border border-slate-200 p-2 rounded-lg text-xs text-slate-500 cursor-not-allowed">
      </div>

      <div>
        <label class="block font-semibold text-slate-500 mb-1">Department</label>
        <input type="text" name="department" value="General Operations"
          class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs">
      </div>

      <div>
        <label class="block font-semibold text-slate-500 mb-1">Remarks <span class="text-slate-400 font-normal">(optional)</span></label>
        <textarea name="remarks" rows="2" placeholder="Reason for return, condition, etc."
          class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs resize-none"></textarea>
      </div>

      <div>
        <label class="block font-semibold text-slate-500 mb-1">Upload Return-to-Store Slip <span class="text-rose-500 font-black">*</span></label>
        <input type="file" name="return_file" required accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.doc,.docx"
          class="w-full bg-amber-50 border border-amber-200 text-slate-700 text-[10px] p-2 rounded-lg">
        <p class="text-[10px] text-amber-700 mt-0.5">&#9888; Return-to-Store Slip is mandatory</p>
      </div>

      <button type="submit" class="w-full bg-amber-500 hover:bg-amber-600 text-white p-2.5 rounded-xl font-bold tracking-wide transition-all text-xs">&#8634; Record Return to Store</button>
    </form>
  </div>

  </div><!-- end grid -->
</div>

<script id="mm-held" type="application/json">{held_json}</script>
<script id="mm-held-units" type="application/json">{held_units_json}</script>
<script>
var MMHELD = JSON.parse(document.getElementById('mm-held').textContent);
var MMHELD_UNITS = JSON.parse(document.getElementById('mm-held-units').textContent);
function onRtsEmployeeChange() {{
    var emp = document.getElementById('rts_employee').value;
    var itemSel = document.getElementById('rts_item');
    var panel = document.getElementById('rts_held_panel');
    var noBox = document.getElementById('rts_no_items');
    var listDiv = document.getElementById('rts_held_list');
    var qty = document.getElementById('rts_qty');
    var qtyHelp = document.getElementById('rts_qty_help');
    var uomDisp = document.getElementById('rts_uom_display');
    var catDisp = document.getElementById('rts_category_display');
    var serialBlock = document.getElementById('rts_serial_block');
    var serialSel = document.getElementById('rts_asset_unit');
    itemSel.innerHTML = '<option value="">-- Select item --</option>';
    uomDisp.value = ''; qty.value = 1; qty.max = ''; qtyHelp.textContent = 'Max: \u2014';
    if (catDisp) catDisp.value = '';
    if (serialBlock) {{ serialBlock.classList.add('hidden'); serialSel.required=false; serialSel.value=''; }}

    if (!emp) {{
        itemSel.disabled = true; panel.classList.add('hidden'); noBox.classList.add('hidden'); return;
    }}
    var consumRows = MMHELD[emp] || [];
    var unitRows = MMHELD_UNITS[emp] || [];
    if (!consumRows.length && !unitRows.length) {{
        itemSel.disabled = true; panel.classList.add('hidden'); noBox.classList.remove('hidden'); return;
    }}
    noBox.classList.add('hidden');
    panel.classList.remove('hidden');

    var consumDisplay = consumRows.map(function(r) {{
        return '<div class="flex justify-between gap-2 border-b border-amber-100 last:border-0 pb-1">' +
            '<span class="truncate"><b>' + r.name + '</b> <span class="text-slate-400 text-[10px]">(' + r.code + ')</span></span>' +
            '<span class="font-mono text-amber-700 font-bold shrink-0">' + r.qty_held + ' ' + r.uom + '</span></div>';
    }}).join('');
    // Group tracked rows by item_id for the held panel + dropdown
    var byItem = {{}};
    unitRows.forEach(function(u) {{
        if (!byItem[u.item_id]) byItem[u.item_id] = {{ name: u.item_name, code: u.item_code, uom: u.uom, category: u.category, serials: [] }};
        byItem[u.item_id].serials.push({{ id: u.asset_unit_id, sn: u.serial_no }});
    }});
    var unitDisplay = Object.keys(byItem).map(function(iid) {{
        var g = byItem[iid];
        var serialList = g.serials.map(function(s){{return s.sn;}}).join(', ');
        return '<div class="border-b border-amber-100 last:border-0 pb-1">' +
            '<div class="flex justify-between gap-2"><span class="truncate"><b>' + g.name + '</b> <span class="text-slate-400 text-[10px]">(' + g.code + ')</span></span>' +
            '<span class="font-mono text-amber-700 font-bold shrink-0">' + g.serials.length + ' ' + g.uom + '</span></div>' +
            '<div class="text-[9px] text-slate-500 font-mono mt-0.5">' + serialList + '</div></div>';
    }}).join('');
    listDiv.innerHTML = consumDisplay + unitDisplay;

    consumRows.forEach(function(r) {{
        var opt = document.createElement('option');
        opt.value = r.item_id;
        opt.textContent = r.name + ' (' + r.code + ') \u2014 holding ' + r.qty_held + ' ' + r.uom;
        opt.dataset.uom = r.uom; opt.dataset.max = r.qty_held;
        opt.dataset.category = r.category || ''; opt.dataset.tracked = '0';
        itemSel.appendChild(opt);
    }});
    Object.keys(byItem).forEach(function(iid) {{
        var g = byItem[iid];
        var opt = document.createElement('option');
        opt.value = iid;
        opt.textContent = g.name + ' (' + g.code + ') \u2014 ' + g.serials.length + ' serial(s) held';
        opt.dataset.uom = g.uom; opt.dataset.max = g.serials.length;
        opt.dataset.category = g.category || ''; opt.dataset.tracked = '1';
        opt.dataset.serials = JSON.stringify(g.serials);
        itemSel.appendChild(opt);
    }});
    itemSel.disabled = false;
}}
function onRtsItemChange() {{
    var sel = document.getElementById('rts_item');
    var opt = sel.options[sel.selectedIndex];
    var qty = document.getElementById('rts_qty');
    var qtyHelp = document.getElementById('rts_qty_help');
    var uomDisp = document.getElementById('rts_uom_display');
    var catDisp = document.getElementById('rts_category_display');
    var serialBlock = document.getElementById('rts_serial_block');
    var serialSel = document.getElementById('rts_asset_unit');
    if (!opt || !opt.value) {{
        uomDisp.value = ''; qty.max = ''; qtyHelp.textContent = 'Max: \u2014';
        if (catDisp) catDisp.value = '';
        if (serialBlock) {{ serialBlock.classList.add('hidden'); serialSel.required=false; serialSel.value=''; }}
        return;
    }}
    uomDisp.value = opt.dataset.uom || '';
    if (catDisp) catDisp.value = opt.dataset.category || '';
    qty.max = opt.dataset.max || '';
    qty.value = 1;
    qtyHelp.textContent = 'Max: ' + (opt.dataset.max || '\u2014') + ' ' + (opt.dataset.uom || '');
    if (opt.dataset.tracked === '1' && serialBlock) {{
        var serials = JSON.parse(opt.dataset.serials || '[]');
        serialSel.innerHTML = '<option value="">-- Select serial being returned --</option>';
        serials.forEach(function(s) {{
            var o = document.createElement('option');
            o.value = s.id; o.textContent = s.sn;
            serialSel.appendChild(o);
        }});
        serialBlock.classList.remove('hidden');
        serialSel.required = true;
        qty.value = 1; qty.readOnly = true;
    }} else if (serialBlock) {{
        serialBlock.classList.add('hidden');
        serialSel.required = false; serialSel.value = '';
        qty.readOnly = false;
    }}
}}
</script>

<script id="mm-inv" type="application/json">{inv_json}</script>
<script id="mm-units-by-item" type="application/json">{units_by_item_json}</script>
<script>
var MMINV = JSON.parse(document.getElementById('mm-inv').textContent);
var MM_UNITS_BY_ITEM = JSON.parse(document.getElementById('mm-units-by-item').textContent);
function mkDd(items, cls) {{
    return items.slice(0,10).map(function(i) {{
        return '<div class="p-2.5 hover:bg-indigo-50 cursor-pointer border-b border-slate-100 last:border-0 ' + cls + '"'
            + ' data-id="'+i.id+'"'
            + ' data-name="'+i.name.replace(/"/g,"&quot;")+'"'
            + ' data-code="'+i.code+'"'
            + ' data-stock="'+i.stock+'"'
            + ' data-uom="'+i.uom+'"'
            + ' data-price="'+i.price+'"'
            + ' data-vendor="'+i.vendor+'"'
            + ' data-category="'+(i.category||'')+'"'
            + ' data-tracked="'+(i.tracked?'1':'0')+'">'
            + '<div class="font-semibold text-xs pointer-events-none">'+i.name+(i.tracked?'<span class="ml-1 bg-amber-100 text-amber-700 text-[9px] font-bold px-1.5 py-0.5 rounded">TRACKED</span>':'')+'</div>'
            + '<div class="text-[10px] text-slate-400 pointer-events-none">'+i.code+' | Stock: '+i.stock+'</div></div>';
    }}).join('') || '<div class="p-3 text-slate-400 text-xs">No items found</div>';
}}

// Auto-fill serial textarea: prompts for prefix + start number, generates N serials.
function autoFillSerials() {{
    var qtyInput = document.querySelector('form[action="/transaction"] [name=quantity]');
    var qty = parseInt((qtyInput && qtyInput.value) || '0', 10);
    if (qty <= 0) {{ alert('Set Quantity Received first.'); return; }}
    var codeFallback = document.getElementById('inward_item_search').value.match(/\\(([^)]+)\\)/);
    codeFallback = codeFallback ? codeFallback[1] : 'EIPL';
    var prefix = window.prompt('Enter serial prefix (without trailing dash):', codeFallback);
    if (!prefix) return;
    var startStr = window.prompt('Starting number (e.g. 1):', '1');
    var start = parseInt(startStr, 10);
    if (isNaN(start) || start < 0) return;
    var lines = [];
    for (var i = 0; i < qty; i++) {{
        lines.push(prefix + '-' + String(start + i).padStart(3, '0'));
    }}
    document.getElementById('inward_serial_numbers').value = lines.join('\\n');
}}

function filterInwardItems(q) {{
    var dd=document.getElementById('inward_item_dropdown');
    var m=q ? MMINV.filter(function(i){{return i.name.toLowerCase().includes(q.toLowerCase())||i.code.toLowerCase().includes(q.toLowerCase());}}) : [];
    if(!q){{dd.classList.add('hidden');return;}}
    dd.innerHTML=mkDd(m,'inw-item'); dd.classList.remove('hidden');
}}
function showInwardDropdown(){{filterInwardItems(document.getElementById('inward_item_search').value);}}
function filterMISItems(q) {{
    var dd=document.getElementById('mis_item_dropdown');
    var m=q ? MMINV.filter(function(i){{return i.name.toLowerCase().includes(q.toLowerCase())||i.code.toLowerCase().includes(q.toLowerCase());}}) : [];
    if(!q){{dd.classList.add('hidden');return;}}
    dd.innerHTML=mkDd(m,'mis-item'); dd.classList.remove('hidden');
}}
function showMISDropdown(){{filterMISItems(document.getElementById('mis_item_search').value);}}
document.addEventListener('click',function(e){{
    var el=e.target.closest('.inw-item');
    if(el){{
        var tracked = el.dataset.tracked === '1';
        document.getElementById('inward_item_id').value=el.dataset.id;
        document.getElementById('inward_item_search').value=el.dataset.name+' ('+el.dataset.code+')';
        document.getElementById('inward_selected_label').textContent='Selected: '+el.dataset.name+' | Stock: '+el.dataset.stock+(tracked?' | TRACKED':'');
        document.getElementById('inward_selected_label').className='text-[10px] text-indigo-600 font-semibold mt-1';
        document.getElementById('inward_item_dropdown').classList.add('hidden');
        if(el.dataset.uom)document.getElementById('inward_uom_select').value=el.dataset.uom;
        if(document.getElementById('inward_category_display'))document.getElementById('inward_category_display').value=el.dataset.category||'';
        // Show/hide Serial Numbers block based on tracking
        var sb = document.getElementById('inward_serial_block');
        var ta = document.getElementById('inward_serial_numbers');
        if (tracked) {{
            sb.classList.remove('hidden');
            ta.required = true;
        }} else {{
            sb.classList.add('hidden');
            ta.value = '';
            ta.required = false;
        }}
        return;
    }}
    var el2=e.target.closest('.mis-item');
    if(el2){{
        var tracked2 = el2.dataset.tracked === '1';
        document.getElementById('mis_item_id').value=el2.dataset.id;
        document.getElementById('mis_item_search').value=el2.dataset.name+' ('+el2.dataset.code+')';
        document.getElementById('mis_selected_label').textContent='Selected: '+el2.dataset.name+' | Stock: '+el2.dataset.stock+(tracked2?' | TRACKED':'');
        document.getElementById('mis_uom_display').value=el2.dataset.uom||'';
        if(document.getElementById('mis_category_display'))document.getElementById('mis_category_display').value=el2.dataset.category||'';
        document.getElementById('mis_item_dropdown').classList.add('hidden');
        // Show/hide MIS serial picker
        var sblk = document.getElementById('mis_serial_block');
        var sel = document.getElementById('mis_asset_unit');
        var misQty = document.querySelector('form[action="/material/issue"] [name=quantity]');
        if (tracked2) {{
            sblk.classList.remove('hidden');
            sel.required = true;
            sel.innerHTML = '<option value="">-- Select serial in stock --</option>';
            var units = MM_UNITS_BY_ITEM[el2.dataset.id] || [];
            units.forEach(function(u) {{
                var opt = document.createElement('option');
                opt.value = u.id; opt.textContent = u.serial_no;
                sel.appendChild(opt);
            }});
            if (misQty) {{ misQty.value = 1; misQty.readOnly = true; }}
        }} else {{
            sblk.classList.add('hidden');
            sel.required = false; sel.value = '';
            if (misQty) {{ misQty.readOnly = false; }}
        }}
        return;
    }}
    if(document.getElementById('inward_item_dropdown')&&!document.getElementById('inward_item_dropdown').contains(e.target)&&e.target.id!=='inward_item_search')document.getElementById('inward_item_dropdown').classList.add('hidden');
    if(document.getElementById('mis_item_dropdown')&&!document.getElementById('mis_item_dropdown').contains(e.target)&&e.target.id!=='mis_item_search')document.getElementById('mis_item_dropdown').classList.add('hidden');
}});
</script>
</div><!-- end flex-1 -->
</body></html>"""
    return HTMLResponse(html_page)


@app.get("/", response_class=HTMLResponse)
def root_dashboard(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    items = db.query(models.Item).all()
    assignments = db.query(models.MaterialAssignment).all()
    employees = db.query(models.Employee).all()
    users = db.query(models.User).all()

    # Per-item transaction logs for the merged log column / modal
    import json as _json_txn
    txn_logs = build_txn_logs(db, items)

    # Per-item asset register for the Serials modal (tracked items)
    asset_register = {}
    for u in db.query(models.AssetUnit).order_by(models.AssetUnit.acquired_at.asc()).all():
        asset_register.setdefault(u.item_id, []).append({
            "serial_no": u.serial_no or "—",
            "status": u.status or "In Stock",
            "current_holder": u.current_holder or "",
            "acquired_at": fmt_ist(u.acquired_at, "%d-%m-%Y"),
            "notes": u.notes or "",
        })

    item_options = "".join([f'<option value="{i.id}">{i.name} ({i.item_code})</option>' for i in items])
    employee_options = "".join([f'<option value="{e.name}">{e.name} - {e.role_title}</option>' for e in employees])

    # 1. FIXED MODAL SCRIPT ENGINE BLOCK WITH ADDED DEPARTMENT INPUT
    inventory_rows = """
    <script>
    // 1. THE CORRECTED PROCUREMENT REQUEST MODAL ENGINE
    window.openProcurementModal = function(id, name, item_code) {
        let modal = document.getElementById('dynamicProcurementModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'dynamicProcurementModal';
            modal.className = 'fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50';
            document.body.appendChild(modal);
        }
        modal.innerHTML = `
            <div class="bg-white rounded-xl border border-slate-200 shadow-2xl w-full max-w-md p-6 text-left relative">
                <h3 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2" style="font-size: 1.125rem; font-weight: 700; color: #0f172a; margin-bottom: 1rem;">📋 Create Procurement Request</h3>
                <form action="/procurement/request" method="POST" style="display: flex; flex-direction: column; gap: 1rem;">
                    <input type="hidden" name="item_id" value="` + id + `">
                    <div>
                        <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Item Name</label>
                        <input type="text" value="` + name + `" readonly style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; color: #64748b; background-color: #f8fafc;">
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Item Code</label>
                        <input type="text" value="` + item_code + `" readonly style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; font-family: monospace; color: #64748b; background-color: #f8fafc;">
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Target Department</label>
                        <select name="department" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; color: #0f172a; background-color: #ffffff;">
                            <option value="Operations">Operations</option>
                            <option value="Mechanical">Mechanical</option>
                            <option value="Electrical">Electrical</option>
                            <option value="Commercial">Commercial</option>
                            <option value="Stores">Stores</option>
                        </select>
                    </div>
                    <div>
                        <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Quantity Required</label>
                        <input type="number" name="quantity" min="1" value="1" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem;">
                    </div>
                    <div style="display: flex; justify-content: flex-end; gap: 0.5rem; padding-top: 0.75rem; border-top: 1px solid #e2e8f0;">
                        <button type="button" onclick="document.getElementById('dynamicProcurementModal').remove()" style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 700; color: #475569; background-color: #f1f5f9; border: none; border-radius: 0.375rem; cursor: pointer;">Cancel</button>
                        <button type="submit" style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 700; color: white; background-color: #4338ca; border: none; border-radius: 0.375rem; cursor: pointer;">Submit Request</button>
                    </div>
                </form>
            </div>
        `;
    };

    // 2. THE EDIT ITEM MENU — styled to match Procure widget panel
    window.openEditItemModal = function(id, name, Unique_code, price, current_stock, minimum_stock, supplier, site) {
        let modal = document.getElementById('dynamicEditItemModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'dynamicEditItemModal';
            modal.className = 'fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50';
            modal.onclick = function(e) { if (e.target === modal) modal.remove(); };
            document.body.appendChild(modal);
        }
        modal.innerHTML = `
            <div style="background:#fff;border-radius:1rem;border:1px solid #e2e8f0;box-shadow:0 25px 50px -12px rgba(0,0,0,0.25);width:100%;max-width:28rem;padding:1.5rem;text-align:left;position:relative;">
                <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #f1f5f9;padding-bottom:0.75rem;margin-bottom:1.25rem;">
                    <div>
                        <h3 style="font-size:0.75rem;font-weight:800;color:#0f172a;text-transform:uppercase;letter-spacing:0.05em;">&#9998; Edit Inventory Item</h3>
                        <p style="font-size:0.625rem;color:#94a3b8;margin-top:0.125rem;">Update item details and stock levels</p>
                    </div>
                    <button type="button" onclick="document.getElementById('dynamicEditItemModal').remove()"
                        style="color:#94a3b8;background:#f8fafc;border:none;border-radius:0.5rem;padding:0.375rem 0.5rem;cursor:pointer;font-size:0.75rem;">&#10005;</button>
                </div>
                <form action="/items/edit/` + id + `" method="POST" style="display:flex;flex-direction:column;gap:0.875rem;">
                    <div>
                        <label style="display:block;font-size:0.65rem;font-weight:700;color:#4338ca;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">&#9670; Unique Item Code</label>
                        <input type="text" name="item_code" value="` + Unique_code + `" required
                            style="width:100%;padding:0.625rem 0.75rem;border:2px solid #6366f1;border-radius:0.625rem;font-size:0.8rem;font-family:monospace;color:#0f172a;background:#fafafa;box-sizing:border-box;text-transform:uppercase;"
                            oninput="this.value=this.value.toUpperCase()">
                    </div>
                    <div>
                        <label style="display:block;font-size:0.65rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Item Name</label>
                        <input type="text" name="name" value="` + name + `" required
                            style="width:100%;padding:0.625rem 0.75rem;border:1px solid #e2e8f0;border-radius:0.625rem;font-size:0.8rem;color:#0f172a;background:#f8fafc;box-sizing:border-box;">
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;">
                        <div>
                            <label style="display:block;font-size:0.65rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Price (&#8377;)</label>
                            <input type="number" step="0.01" name="price" value="` + price + `" required
                                style="width:100%;padding:0.625rem 0.75rem;border:1px solid #e2e8f0;border-radius:0.625rem;font-size:0.8rem;font-family:monospace;color:#1e293b;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;font-size:0.65rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Safety Stock</label>
                            <input type="number" name="minimum_stock" value="` + minimum_stock + `" required
                                style="width:100%;padding:0.625rem 0.75rem;border:1px solid #e2e8f0;border-radius:0.625rem;font-size:0.8rem;font-family:monospace;color:#1e293b;box-sizing:border-box;">
                        </div>
                    </div>
                    <div>
                        <label style="display:block;font-size:0.65rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Current Stock Level</label>
                        <input type="number" name="current_stock" value="` + current_stock + `" required
                            style="width:100%;padding:0.625rem 0.75rem;border:1px solid #e2e8f0;border-radius:0.625rem;font-size:0.8rem;font-family:monospace;color:#1e293b;box-sizing:border-box;">
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;">
                        <div>
                            <label style="display:block;font-size:0.65rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Supplier / Vendor</label>
                            <input type="text" name="supplier" value="` + (supplier||'') + `"
                                style="width:100%;padding:0.625rem 0.75rem;border:1px solid #e2e8f0;border-radius:0.625rem;font-size:0.8rem;color:#1e293b;background:#f8fafc;box-sizing:border-box;" placeholder="Vendor name">
                        </div>
                        <div>
                            <label style="display:block;font-size:0.65rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.25rem;">Storage Site</label>
                            <input type="text" name="storage_site" value="` + (site||'') + `"
                                style="width:100%;padding:0.625rem 0.75rem;border:1px solid #e2e8f0;border-radius:0.625rem;font-size:0.8rem;color:#1e293b;background:#f8fafc;box-sizing:border-box;" placeholder="e.g. Store Yard">
                        </div>
                    </div>
                    <div style="display:flex;justify-content:flex-end;gap:0.5rem;padding-top:0.75rem;border-top:1px solid #f1f5f9;margin-top:0.25rem;">
                        <button type="button" onclick="document.getElementById('dynamicEditItemModal').remove()"
                            style="padding:0.5rem 1.125rem;font-size:0.7rem;font-weight:700;color:#475569;background:#f1f5f9;border:none;border-radius:0.5rem;cursor:pointer;">Cancel</button>
                        <button type="submit"
                            style="padding:0.5rem 1.125rem;font-size:0.7rem;font-weight:700;color:white;background:#d97706;border:none;border-radius:0.5rem;cursor:pointer;">&#10003; Save Changes</button>
                    </div>
                </form>
            </div>
        `;
    };
    </script>
    """

    for it in items:
        alert_status = ""
        if it.current_stock <= it.minimum_stock:
            alert_status = ' <span class="text-rose-600 font-black animate-pulse">&#9888;&#65039; LOW</span>'
        
        item_cat = getattr(it, 'category', None) or DEFAULT_ASSET_CLASS
        item_sup = getattr(it, 'supplier', 'EIPL Approved Vendor')
        item_site = getattr(it, 'storage_site', 'Store Yard')

        import html as _html
        h_name = _html.escape(it.name, quote=True)
        h_code = _html.escape(it.item_code, quote=True)
        h_vendor = _html.escape(item_sup, quote=True)
        h_uom = _html.escape(getattr(it, 'uom', '') or '', quote=True)
        h_cat = _html.escape(item_cat, quote=True)

        if current_user.role == "Admin":
            admin_only_cells = f"""
            <td class="p-3 text-slate-600 text-[11px] font-medium text-center">{item_sup}</td>
            <td class="p-3 font-mono text-slate-600 text-center">&#8377;{it.price:,.2f}</td>"""
            action_cell = f"""
            <td class="p-3">
                <div class="flex items-center gap-2">
                    <button type="button"
                        data-action="create-indent"
                        data-id="{it.id}" data-name="{h_name}" data-code="{h_code}"
                        data-uom="{h_uom}" data-dept="{_html.escape(item_site, quote=True)}"
                        class="text-indigo-600 hover:underline font-bold text-[11px]">+ Indent</button>
                    <button type="button"
                        data-action="edit-item"
                        data-id="{it.id}" data-name="{h_name}" data-code="{h_code}"
                        data-price="{it.price}" data-stock="{it.current_stock}" data-minstock="{it.minimum_stock}"
                        data-supplier="{h_vendor}" data-site="{_html.escape(item_site, quote=True)}"
                        data-category="{h_cat}"
                        class="text-amber-600 hover:underline font-bold text-[11px]">Edit</button>
                    <form action="/items/delete/{it.id}" method="POST" class="inline m-0 delete-protected-form" onsubmit="event.preventDefault(); openAdminDeleteModal(this, 'Delete item: {it.name} ({it.item_code})?');">
                        <button type="submit" class="text-rose-600 hover:underline font-bold text-[11px] bg-transparent border-none p-0 cursor-pointer inline">Delete</button>
                    </form>
                </div>
            </td>"""
        else:
            admin_only_cells = ""
            action_cell = f"""
            <td class="p-3">
                <button type="button"
                    data-action="create-indent"
                    data-id="{it.id}" data-name="{h_name}" data-code="{h_code}"
                    data-uom="{h_uom}" data-dept="{_html.escape(item_site, quote=True)}"
                    class="text-indigo-600 hover:underline font-bold text-[11px]">+ Indent</button>
            </td>"""

        inventory_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/50" data-row="1">
            <td class="p-3 font-semibold text-slate-900">
                <span>{it.name}</span>{alert_status}
                <div class="text-[10px] text-slate-400 mt-0.5">
                    <span class="bg-blue-50 px-1 py-0.5 rounded text-blue-600">{item_site}</span>
                </div>
            </td>
            <td class="p-3 font-mono text-[11px] text-slate-500">{it.item_code}</td>
            <td class="p-3 text-center">
                <span class="bg-slate-100 px-2 py-0.5 rounded text-slate-600 text-[10px] font-semibold whitespace-nowrap">{item_cat}</span>
            </td>
            {admin_only_cells}
            <td class="p-3 font-mono font-bold text-slate-900" data-sort="{it.current_stock}">
                {it.current_stock}
                <span class="lot-toggle text-[10px] text-indigo-500 font-semibold cursor-pointer underline ml-1" data-target="lot-row-{it.id}">vendors</span>
            </td>
            <td class="p-3 font-mono text-slate-400" data-sort="{it.minimum_stock}">{it.minimum_stock}</td>
            {action_cell}
            <td class="p-3 text-center">
                <div class="flex items-center justify-center gap-1 flex-wrap">
                    <button type="button"
                        onclick="openTxnLog({it.id}, '{h_name}', '{h_code}')"
                        class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all inline-flex items-center gap-1">
                        <i class="fa-solid fa-book-open text-[9px]"></i> Log
                    </button>
                    {f'''<button type="button"
                        onclick="openAssetRegister({it.id}, '{h_name}', '{h_code}')"
                        class="bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all inline-flex items-center gap-1">
                        <i class="fa-solid fa-barcode text-[9px]"></i> Serials
                    </button>''' if is_tracked(it) else ''}
                </div>
            </td>
        </tr>
        <script>window.__txnData = window.__txnData||{{}};window.__txnData[{it.id}]={_json_txn.dumps(txn_logs.get(it.id, []))};window.__assetData = window.__assetData||{{}};window.__assetData[{it.id}]={_json_txn.dumps(asset_register.get(it.id, []))};</script>
        """

        # Multi-vendor / multi-price lot breakdown — hidden by default, toggled via "vendors" link.
        lots = db.query(models.ItemLot).filter(
            models.ItemLot.item_id == it.id,
            models.ItemLot.quantity > 0
        ).order_by(models.ItemLot.received_at.asc()).all()

        n_cols = 8 if current_user.role == "Admin" else 6
        if lots:
            lot_lines = "".join(
                f"""<div class="flex items-center justify-between gap-3 py-1 px-2 odd:bg-white even:bg-slate-50 rounded">
                        <span class="font-medium text-slate-600">{_html.escape(lot.vendor, quote=True)}</span>
                        <span class="font-mono text-slate-400">&#8377;{lot.price:,.2f}</span>
                        <span class="font-mono font-bold text-slate-800">{lot.quantity} {h_uom or ''}</span>
                    </div>"""
                for lot in lots
            )
        else:
            lot_lines = '<div class="text-slate-400 italic px-2 py-1">No vendor lot records yet — recorded as a single combined balance.</div>'

        inventory_rows += f"""
        <tr id="lot-row-{it.id}" class="lot-detail-row hidden bg-slate-50/70 border-b border-slate-100">
            <td colspan="{n_cols}" class="p-3">
                <div class="text-[10px] uppercase font-bold text-slate-400 tracking-wider mb-1.5">Vendor / Price Lots for {h_name} (FIFO order — oldest first)</div>
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1 text-[11px]">
                    {lot_lines}
                </div>
                <div class="text-[10px] text-slate-400 mt-1.5">Total Quantity: <span class="font-bold text-slate-600">{it.current_stock} {h_uom or ''}</span> &bull; Outward issues consume the oldest lot first.</div>
            </td>
        </tr>
        """

    req_rows = ""
    reqs = db.query(models.ProcurementRequest).order_by(models.ProcurementRequest.timestamp.desc()).all()
    is_admin = current_user.role == "Admin"

    for r in reqs:
        date_str = fmt_ist(r.timestamp, "%d-%m %H:%M")

        # Status badge
        status_badge_map = {
            "Pending":      '<span class="bg-amber-100 text-amber-700 font-bold px-2 py-0.5 rounded text-[10px]">Pending</span>',
            "Order Pending":'<span class="bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded text-[10px]">Order Pending</span>',
            "Order Placed": '<span class="bg-indigo-100 text-indigo-700 font-bold px-2 py-0.5 rounded text-[10px]">Order Placed</span>',
            "Delivered":    '<span class="bg-emerald-100 text-emerald-700 font-bold px-2 py-0.5 rounded text-[10px]">&#10003; Delivered</span>',
            "Rejected":     '<span class="bg-rose-100 text-rose-700 font-bold px-2 py-0.5 rounded text-[10px]">Rejected</span>',
        }
        badge = status_badge_map.get(r.status, f'<span class="bg-slate-100 text-slate-600 font-bold px-2 py-0.5 rounded text-[10px]">{r.status}</span>')

        # Item description and code/spec cells
        if getattr(r, 'is_new_item', False) and not r.item:
            raw_name = r.new_item_name or ""
            if raw_name.startswith("[CODE:"):
                assigned_code = raw_name[len("[CODE:"):raw_name.index("]")]
                real_display_name = raw_name[raw_name.index("]") + 1:].strip() or "New Item"
                code_cell = f"<span class='bg-emerald-100 text-emerald-700 font-black font-mono px-2 py-0.5 rounded text-[11px] border border-emerald-200'>&#10003; {assigned_code}</span>"
                code_assigned = True
            else:
                real_display_name = raw_name or "Unlisted Item"
                code_cell = f"""<form action='/procurement/assign-code/{r.id}' method='POST' class='flex gap-1 items-center justify-center'>
                        <input type='text' name='new_item_code' placeholder='e.g. EIPL-ST-09' required
                            class='border border-amber-300 bg-amber-50 text-slate-900 font-mono text-[11px] px-2 py-1 rounded-lg w-28 uppercase focus:outline-none focus:border-indigo-500'
                            style='text-transform:uppercase'>
                        <button type='submit' class='bg-amber-500 hover:bg-amber-600 text-white font-bold text-[10px] px-2 py-1 rounded-lg'>Assign</button>
                    </form>"""
                code_assigned = False

            raw_spec = r.detailed_specification or ""
            spec_missing = (not raw_spec.strip() or raw_spec.strip().lower() == "no specs")
            if spec_missing:
                spec_cell = f"""<form action='/procurement/assign-spec/{r.id}' method='POST' class='flex flex-col gap-1 items-center'>
                        <textarea name='specification' rows='2' placeholder='Enter specs...' required
                            class='border border-rose-300 bg-rose-50 text-slate-900 text-[11px] px-2 py-1 rounded-lg w-36 focus:outline-none focus:border-indigo-500 resize-none'></textarea>
                        <button type='submit' class='bg-rose-500 hover:bg-rose-600 text-white font-bold text-[10px] px-2 py-1 rounded-lg'>Submit</button>
                    </form>"""
                spec_filled = False
            else:
                spec_cell = f"<span class='bg-emerald-100 text-emerald-700 font-bold px-2 py-0.5 rounded text-[11px] border border-emerald-200' title='{raw_spec}'>&#10003; Spec Added</span>"
                spec_filled = True

            item_desc_display = f"<span class='text-amber-600 font-bold'>[NEW]</span> <b>{real_display_name}</b><br><span class='text-[10px] text-slate-400 italic font-normal'>Specs: {r.detailed_specification or 'No Specs'}</span>"
            est_value_text = "&#8377; TBD"
        else:
            item_name_str = r.item.name if r.item else (r.new_item_name or "Catalog Item Request")
            item_code_str = f" ({r.item.item_code})" if r.item else ""
            item_desc_display = f"<b>{item_name_str}</b>{item_code_str}"
            est_value_text = f"&#8377;{r.total_estimated_cost:,.2f}" if r.total_estimated_cost else "&#8377;0.00"
            code_cell = "<span class='text-slate-400 text-[10px]'>&#8212;</span>"
            spec_cell = "<span class='text-slate-400 text-[10px]'>&#8212;</span>"
            code_assigned = True
            spec_filled = True

        if getattr(r, 'department', None):
            item_desc_display += f" <span class='text-[10px] text-indigo-600 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded'>[{r.department}]</span>"

        # Workflow execution column
        import html as _html
        flow = ""
        if r.status == "Pending":
            edit_btn = ""
            if is_admin or r.requested_by_id == current_user.id:
                h_dept = _html.escape(r.department or "", quote=True)
                cur_item_id = r.item_id if r.item_id else 0
                edit_btn = f"""<button data-action="edit-request" data-id="{r.id}" data-qty="{r.quantity}" data-dept="{h_dept}" data-itemid="{cur_item_id}" class="text-indigo-600 font-bold hover:underline text-[10px]">Edit</button>"""
            if is_admin:
                if not code_assigned:
                    approve_btn = "<span class='text-[10px] text-slate-400 italic'>Assign code first &#8593;</span>"
                elif not spec_filled:
                    approve_btn = "<span class='text-[10px] text-slate-400 italic'>Add spec first &#8593;</span>"
                else:
                    approve_btn = f"""<form action="/procurement/action/{r.id}/accept" method="POST" class="inline"><input type="submit" value="Approve" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-1.5 py-0.5 rounded cursor-pointer text-[10px]"></form>"""
                flow = f"""<div class="flex items-center gap-1 justify-center">{edit_btn} {approve_btn}
                    <form action="/procurement/action/{r.id}/reject" method="POST" class="inline"><input type="submit" value="Reject" class="bg-rose-600 hover:bg-rose-700 text-white font-bold px-1.5 py-0.5 rounded cursor-pointer text-[10px]"></form>
                    </div>"""
            else:
                flow = f"""<div class="flex items-center gap-1 justify-center">{edit_btn}<span class="text-slate-400 italic text-[10px]">Awaiting Review</span></div>"""

        elif r.status == "Order Pending":
            po_name = _html.escape(r.item.name if r.item else (r.new_item_name or "Item"), quote=True)
            po_code = _html.escape(r.item.item_code if r.item else "N/A", quote=True)
            print_btn = f"""<button data-action="print-po" data-id="{r.id}" data-name="{po_name}" data-code="{po_code}" data-qty="{r.quantity}" class="bg-slate-700 hover:bg-slate-800 text-white text-[10px] font-bold px-2 py-0.5 rounded">&#128438; Print PO</button>"""
            has_pricing = bool(r.vendor and r.vendor.strip()) and (r.unit_price is not None)
            if is_admin:
                cur_vendor = _html.escape(r.vendor or "", quote=True)
                cur_rate = f"{r.unit_price:.2f}" if r.unit_price is not None else ""
                # Admin enters vendor + rate here; the Order button unlocks only after both are saved
                pricing_form = f"""<form action="/procurement/set-pricing/{r.id}" method="POST" class="flex items-center gap-1 justify-center flex-wrap">
                        <input type="text" name="vendor" value="{cur_vendor}" placeholder="Vendor" required
                            class="border border-slate-300 bg-white text-slate-900 text-[10px] px-1.5 py-1 rounded-lg w-24 focus:outline-none focus:border-indigo-500">
                        <input type="number" step="0.01" min="0" name="unit_price" value="{cur_rate}" placeholder="Rate &#8377;" required
                            class="border border-slate-300 bg-white text-slate-900 font-mono text-[10px] px-1.5 py-1 rounded-lg w-20 focus:outline-none focus:border-indigo-500">
                        <button type="submit" class="bg-amber-500 hover:bg-amber-600 text-white font-bold text-[10px] px-2 py-1 rounded-lg">Save</button>
                    </form>"""
                if has_pricing:
                    order_btn = f"""<form action="/procurement/order/{r.id}" method="POST" class="inline"><input type="submit" value="Order" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-2 py-0.5 rounded cursor-pointer text-[10px]"></form>"""
                else:
                    order_btn = """<span class="bg-slate-200 text-slate-400 font-bold px-2 py-0.5 rounded text-[10px] cursor-not-allowed" title="Enter vendor & rate to enable">Order</span>"""
                flow = f"""<div class="flex flex-col items-center gap-1.5">{pricing_form}<div class="flex items-center gap-1 justify-center">{print_btn} {order_btn}</div></div>"""
            else:
                vendor_note = f"<span class='text-[10px] text-slate-500'>Vendor: <b>{_html.escape(r.vendor)}</b></span>" if has_pricing else "<span class='text-[10px] text-slate-400 italic'>Awaiting vendor &amp; rate</span>"
                flow = f"""<div class="flex flex-col items-center gap-1">{print_btn}{vendor_note}</div>"""

        elif r.status == "Order Placed":
            po_name = _html.escape(r.item.name if r.item else (r.new_item_name or "Item"), quote=True)
            po_code = _html.escape(r.item.item_code if r.item else "N/A", quote=True)
            flow = f"""<div class="flex justify-center"><button data-action="print-po" data-id="{r.id}" data-name="{po_name}" data-code="{po_code}" data-qty="{r.quantity}" class="bg-slate-700 hover:bg-slate-800 text-white text-[10px] font-bold px-2 py-0.5 rounded">&#128438; Print PO</button></div>"""

        elif r.status == "Delivered":
            flow = """<div class="flex justify-center"><span class="text-emerald-600 font-bold text-[10px]">&#10003; Delivered</span></div>"""

        else:
            flow = """<div class="flex justify-center"><span class="text-slate-400 line-through text-[11px]">Closed</span></div>"""

        # Est Value: only show for admin
        est_td = f'<td class="p-3 font-mono text-slate-600 text-center whitespace-nowrap" data-sort="{r.total_estimated_cost or 0}">{est_value_text}</td>' if is_admin else ""

        # Build message thread
        messages = db.query(models.ProcurementMessage).filter(
            models.ProcurementMessage.request_id == r.id
        ).order_by(models.ProcurementMessage.timestamp.asc()).all()

        msg_bubbles = ""
        for msg in messages:
            sender_role = msg.sender.role if msg.sender else "Staff"
            sender_label = "Admin" if sender_role == "Admin" else (msg.sender.username if msg.sender else "Staff")
            bubble_color = "bg-indigo-50 border-indigo-100 text-indigo-900" if sender_role == "Admin" else "bg-slate-50 border-slate-200 text-slate-800"
            label_color = "text-indigo-600" if sender_role == "Admin" else "text-slate-500"
            msg_time = fmt_ist(msg.timestamp, "%d-%m %H:%M")
            safe_msg = _html.escape(msg.message)
            msg_bubbles += f"""<div class='border rounded-lg p-2 {bubble_color} mb-1'>
                <div class='flex justify-between items-center mb-0.5'>
                    <span class='font-bold text-[10px] {label_color}'>{sender_label}</span>
                    <span class='text-[9px] text-slate-400 font-mono'>{msg_time}</span>
                </div>
                <p class='text-[11px] leading-snug'>{safe_msg}</p>
            </div>"""

        msg_thread_cell = f"""<div class='w-52'>
            <div class='max-h-24 overflow-y-auto mb-1.5 space-y-1 pr-0.5'>
                {msg_bubbles if msg_bubbles else "<p class='text-[10px] text-slate-400 italic'>No messages yet.</p>"}
            </div>
            <form action='/procurement/message/{r.id}' method='POST' class='flex gap-1'>
                <input type='text' name='message' placeholder='Type message...' required
                    class='flex-1 border border-slate-200 bg-slate-50 text-[11px] px-2 py-1 rounded-lg focus:outline-none focus:border-indigo-400 min-w-0'>
                <button type='submit' class='bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] px-2 py-1 rounded-lg shrink-0'>Send</button>
            </form>
        </div>"""

        # Category: falls back to the linked item's category, then default
        req_category = getattr(r, 'category', None) or (getattr(r.item, 'category', None) if r.item else None) or DEFAULT_ASSET_CLASS

        req_rows += f"""<tr class="border-b hover:bg-slate-50 text-xs align-middle" data-row="1" data-date="{fmt_ist(r.timestamp, '%Y-%m-%d')}" data-text="{date_str} {r.requester.username if r.requester else ''} {r.status} {r.department or ''}">
            <td class="p-3 text-slate-500 font-mono whitespace-nowrap text-center">{date_str}</td>
            <td class="p-3 text-slate-800 text-center">{item_desc_display}</td>
            <td class="p-3 font-mono font-semibold text-center">{r.quantity}</td>
            {est_td}
            <td class="p-3 text-center">{code_cell}</td>
            <td class="p-3 text-center">{spec_cell}</td>
            <td class="p-3 text-center"><span class="bg-slate-100 px-2 py-0.5 rounded text-slate-600 text-[10px] font-semibold whitespace-nowrap">{req_category}</span></td>
            <td class="p-3 text-slate-500 whitespace-nowrap text-center">{r.requester.username if r.requester else 'System'}</td>
            <td class="p-3 text-center" data-status="{r.status}">{badge}</td>
            <td class="p-3">{msg_thread_cell}</td>
            <td class="p-3 text-center">{flow}</td>
        </tr>"""


    assigned_rows = ""
    for a in assignments:
        ts = fmt_ist(a.timestamp) or "—"
        item_name = a.item.name if a.item else 'Archived Asset'
        item_category = getattr(a.item, 'category', None) or DEFAULT_ASSET_CLASS if a.item else DEFAULT_ASSET_CLASS
        dept = getattr(a, 'department', '—') or '—'
        is_ret = bool(getattr(a, 'is_return', False))
        if is_ret:
            qty_html = f'<span class="font-mono font-bold text-amber-700">+{a.quantity}</span> <span class="bg-amber-100 text-amber-700 text-[9px] font-black px-1.5 py-0.5 rounded ml-1">RETURN</span>'
            person_label = "Returned by"
        else:
            qty_html = f'<span class="font-mono font-bold text-blue-700">{a.quantity}</span>'
            person_label = "Issued to"
        assigned_rows += f"""<tr class="border-b hover:bg-slate-50 text-xs" data-row="1">
            <td class="p-3 font-mono text-slate-400 text-[11px]">{ts}</td>
            <td class="p-3 font-bold text-slate-800">{item_name}</td>
            <td class="p-3 text-center" data-sort="{a.quantity}">{qty_html}</td>
            <td class="p-3 font-mono text-slate-500 text-center">{a.uom}</td>
            <td class="p-3 text-center"><span class="bg-slate-100 px-2 py-0.5 rounded text-slate-600 text-[10px] font-semibold whitespace-nowrap">{item_category}</span></td>
            <td class="p-3 text-slate-700 font-medium"><span class="text-[9px] text-slate-400 block leading-tight">{person_label}</span>{a.issued_to}</td>
            <td class="p-3 text-slate-500">{dept}</td>
            <td class="p-3 text-slate-400 italic text-[11px]">{a.remarks or '—'}</td>
        </tr>"""

    employee_control_panel = ""
    admin_panel = ""
    user_directory_control_panel = ""

    if current_user.role == "Admin":
        employee_list_markup = ""
        for e in employees:
            import html as _html
            h_emp_name    = _html.escape(e.name, quote=True)
            h_emp_role    = _html.escape(e.role_title, quote=True)
            h_emp_loc     = _html.escape(e.location, quote=True)
            h_emp_contact = _html.escape(e.contact, quote=True)
            employee_list_markup += f"""
            <div class='flex items-center justify-between bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px]'>
                <div class='space-y-0.5'>
                    <p class='font-bold text-slate-800'>{e.name}</p>
                    <p class='text-slate-500 text-[10px]'>{e.role_title} | Location: {e.location}</p>
                    <p class='text-slate-400 font-mono text-[9px]'>Ph: {e.contact}</p>
                </div>
                <div class='flex gap-1.5 ml-2'>
                    <button type='button'
                        data-action="edit-employee"
                        data-id="{e.id}" data-name="{h_emp_name}" data-role="{h_emp_role}"
                        data-loc="{h_emp_loc}" data-contact="{h_emp_contact}"
                        class='text-indigo-600 font-bold hover:underline text-[10px]'>edit</button>
                    <form action='/employees/delete/{e.id}' method='POST' class='inline delete-protected-form' onsubmit="event.preventDefault(); openAdminDeleteModal(this, 'Delete employee: {e.name}?');"><input type='submit' value='delete' class='text-rose-500 font-bold cursor-pointer hover:underline bg-transparent border-0 text-[10px]'></form>
                </div>
            </div>"""

        employee_control_panel = f"""
        <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-xl mb-6">
            <h2 class="text-xs font-black text-slate-500 uppercase tracking-wider border-b pb-2 mb-4">👥 Employee Registration</h2>
            <form action="/employees/add" method="POST" class="space-y-2.5 text-xs mb-4">
                <input type="text" name="name" placeholder="Employee Full Name" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                <input type="text" name="role_title" placeholder="Designation / Role" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                <div class="grid grid-cols-2 gap-2">
                    <input type="text" name="location" placeholder="Work Station Loc" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                    <input type="text" name="contact" placeholder="Contact Mobile" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                </div>
                <button type="submit" class="w-full bg-slate-800 text-white font-bold p-2 rounded-lg">Register Personnel</button>
            </form>
            <div class="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">{employee_list_markup}</div>
        </div>
        """

        admin_panel = ""

        user_list_markup = ""
        for u in users:
            import html as _html
            h_uname = _html.escape(u.full_name, quote=True)
            h_desig = _html.escape(u.designation, quote=True)
            h_loc   = _html.escape(u.workstation_location, quote=True)
            user_list_markup += f"""
            <div class='flex items-center justify-between bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px]'>
                <div>
                    <p class='font-bold text-slate-800'>{u.username} ({u.role})</p>
                    <p class='text-slate-500 text-[10px]'>{u.full_name} - {u.designation}</p>
                </div>
                <div class='flex gap-1.5'>
                    <button type='button'
                        data-action="edit-user"
                        data-id="{u.id}" data-name="{h_uname}" data-desig="{h_desig}"
                        data-loc="{h_loc}" data-role="{u.role}"
                        class='text-indigo-600 font-bold hover:underline text-[10px]'>edit</button>
                    <form action='/admin/users/delete/{u.id}' method='POST' class='inline delete-protected-form' onsubmit="event.preventDefault(); openAdminDeleteModal(this, 'Delete user account: {u.username}?');"><input type='submit' value='delete' class='text-rose-500 font-bold cursor-pointer hover:underline bg-transparent border-0 text-[10px]'></form>
                </div>
            </div>"""

        user_directory_control_panel = f"""
        <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-xl mb-6">
            <h2 class="text-xs font-black tracking-wider text-slate-500 uppercase border-b pb-2 mb-4">❖ Grant user Access</h2>
            <form action="/admin/users/create" method="POST" class="space-y-2 text-xs mb-4">
                <div class="grid grid-cols-2 gap-2">
                    <input type="text" name="username" placeholder="Login User Id" required class="w-full bg-slate-50 border p-2 rounded-lg">
                    <input type="password" name="password" placeholder="Account Password" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <input type="text" name="full_name" placeholder="Full Employee Legal Name" required class="w-full bg-slate-50 border p-2 rounded-lg">
                <div class="grid grid-cols-2 gap-2">
                    <input type="text" name="designation" placeholder="Corporate Title / Designation" required class="w-full bg-slate-50 border p-2 rounded-lg">
                    <input type="text" name="workstation_location" placeholder="Workstation Base Location" required class="w-full bg-slate-50 border p-2 rounded-lg">
                </div>
                <select name="role" class="w-full bg-white font-bold border p-2 rounded-lg"><option value="Staff">Grant Staff Level</option><option value="Admin">Grant Full Admin</option></select>
                <button type="submit" class="w-full bg-indigo-600 text-white p-2 rounded-lg font-bold">Provision Account</button>
            </form>
            <div class="space-y-1.5 max-h-[200px] overflow-y-auto pr-1">{user_list_markup}</div>
        </div>
        """

    import json as _json
    mis_inventory_json_safe = _json.dumps([
        {"id": i.id, "name": i.name, "code": i.item_code, "stock": i.current_stock,
         "uom": getattr(i, 'uom', None) or "", "price": i.price or 0.0, "vendor": getattr(i, 'supplier', '') or ""}
        for i in items
    ])

    est_value_header = '<th class="p-3 text-center whitespace-nowrap cursor-pointer hover:text-indigo-600" onclick="sortTable(\'req\',3)">Est. Value <i class="fa-solid fa-sort text-[9px]"></i></th>' if current_user.role == "Admin" else ""

    return templates.LAYOUT_HTML\
        .replace("__USER__", current_user.username)\
        .replace("__ROLE__", current_user.role)\
        .replace("__USER_FULL_NAME__", current_user.full_name)\
        .replace("__USER_DESIGNATION__", current_user.designation)\
        .replace("__USER_LOCATION__", current_user.workstation_location)\
        .replace("__ADMIN_PANEL__", admin_panel)\
        .replace("__EMPLOYEE_CONTROL_PANEL__", employee_control_panel)\
        .replace("__USER_DIRECTORY_CONTROL_PANEL__", user_directory_control_panel)\
        .replace("__OPTIONS__", item_options)\
        .replace("__EMPLOYEE_OPTIONS__", employee_options)\
        .replace("__INVENTORY_ROWS__", inventory_rows)\
        .replace("__REG_ROWS__", req_rows)\
        .replace("__ASSIGNED_ROWS__", assigned_rows)\
        .replace("__MIS_INVENTORY_JSON__", mis_inventory_json_safe)\
        .replace("__EST_VALUE_HEADER__", est_value_header)\
        .replace("__ASSET_CLASS_OPTIONS_JSON__", _json.dumps(ASSET_CLASSES))\
        .replace("__ASSET_CLASS_OPTIONS__", category_options_html())\
        .replace("__IS_ADMIN__", "true" if current_user.role == "Admin" else "false")