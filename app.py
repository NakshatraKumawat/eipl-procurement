import csv
import hashlib
import random
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

app = FastAPI(title="EIPL Enterprise Procurement Framework")

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
        with engine.connect() as conn:
            existing_cols_emp   = [col['name'] for col in engine.dialect.get_columns(conn, "employees")]
            existing_cols_proc  = [col['name'] for col in engine.dialect.get_columns(conn, "procurement_requests")]
            existing_cols_ma    = [col['name'] for col in engine.dialect.get_columns(conn, "material_assignments")]
            existing_cols_items = [col['name'] for col in engine.dialect.get_columns(conn, "items")]
    except Exception as e:
        print(f"[Migration] Schema inspection error: {e}")

    # --- Phase 2: Apply any missing ALTER TABLE statements ---
    db = SessionLocal()
    try:
        if "location" not in existing_cols_emp:
            db.execute(text("ALTER TABLE employees ADD COLUMN location TEXT DEFAULT 'Not Specified'"))
        if "contact" not in existing_cols_emp:
            db.execute(text("ALTER TABLE employees ADD COLUMN contact TEXT DEFAULT 'Not Specified'"))
        if "department" not in existing_cols_proc:
            db.execute(text("ALTER TABLE procurement_requests ADD COLUMN department TEXT DEFAULT 'Operations'"))
        if "department" not in existing_cols_ma:
            db.execute(text("ALTER TABLE material_assignments ADD COLUMN department TEXT DEFAULT 'General Operations'"))
        if "mis_filename" not in existing_cols_ma:
            db.execute(text("ALTER TABLE material_assignments ADD COLUMN mis_filename TEXT"))
        if "mis_uploaded_by_id" not in existing_cols_ma:
            db.execute(text("ALTER TABLE material_assignments ADD COLUMN mis_uploaded_by_id INTEGER"))
        if "mis_upload_timestamp" not in existing_cols_ma:
            db.execute(text("ALTER TABLE material_assignments ADD COLUMN mis_upload_timestamp DATETIME"))

        # Add uom column to items if missing (locked once first transaction is recorded)
        if "uom" not in existing_cols_items:
            db.execute(text("ALTER TABLE items ADD COLUMN uom TEXT"))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Migration Adaptive Notice] Columns pre-aligned: {e}")
    finally:
        db.close()

    # Ensure procurement_messages table exists (new feature)
    try:
        db2 = SessionLocal()
        db2.execute(text("""
            CREATE TABLE IF NOT EXISTS procurement_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER REFERENCES procurement_requests(id),
                sender_id INTEGER REFERENCES users(id),
                message TEXT,
                timestamp DATETIME
            )
        """))
        db2.commit()
        # Add received_by to grn_records if missing
        try:
            db2.execute(text("ALTER TABLE grn_records ADD COLUMN received_by TEXT"))
            db2.commit()
        except Exception:
            pass
        db2.close()
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
    item_id: str = Form(...),              # "NEW" or existing item id
    quantity: int = Form(...),
    uom: str = Form(...),
    vendor: str = Form(None),
    price: float = Form(None),
    new_item_name: str = Form(None),
    new_item_code: str = Form(None),
    site: str = Form(None),
    grn_file: UploadFile = File(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    # GRN file is mandatory
    if not grn_file or not grn_file.filename:
        return HTMLResponse("<script>alert('GRN Upload is mandatory before recording an Inward Transaction.'); window.history.back();</script>")

    import os, datetime as _dt
    grn_dir = "grn_uploads"
    os.makedirs(grn_dir, exist_ok=True)
    timestamp_str = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if item_id == "NEW_INWARD_ITEM":
        # --- NEW ITEM PATH ---
        if not new_item_name or not new_item_code:
            return HTMLResponse("<script>alert('Item Name and Item Code are required for a new item.'); window.history.back();</script>")
        clean_code = new_item_code.strip().upper()
        # Check uniqueness
        existing = db.query(models.Item).filter(models.Item.item_code == clean_code).first()
        if existing:
            return HTMLResponse(f"<script>alert('Item Code {clean_code} already exists in catalog. Please use Search & Select for existing items.'); window.history.back();</script>")
        new_item = models.Item(
            name=new_item_name.strip(),
            item_code=clean_code,
            current_stock=quantity,
            price=price if price is not None else 0.0,
            supplier=vendor.strip() if vendor else "Approved Vendor",
            storage_site=site.strip() if site else "Store Yard",
            uom=uom,
            minimum_stock=0
        )
        db.add(new_item)
        db.flush()
        item = new_item
    else:
        # --- EXISTING ITEM PATH ---
        item = db.query(models.Item).filter(models.Item.id == int(item_id)).first()
        if not item:
            return HTMLResponse("<script>alert('Item not found.'); window.location='/';</script>")
        # Update price and vendor if provided (prices can change between transactions)
        if price is not None and price > 0:
            item.price = price
        if vendor and vendor.strip():
            item.supplier = vendor.strip()
        # Lock UOM: only set if not already set; once set, it stays fixed
        if not item.uom:
            item.uom = uom
        # Use locked UOM for this transaction
        uom = item.uom
        item.current_stock += quantity

    item_unit_price = item.price if item.price is not None else 0.0

    # current_user is Received By
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
        grn_filename=safe_filename,
        uploaded_by_id=current_user.id
    ))

    # Auto-mark any "Order Placed" procurement for this item as Delivered
    open_orders = db.query(models.ProcurementRequest).filter(
        models.ProcurementRequest.item_id == item.id,
        models.ProcurementRequest.status == "Order Placed"
    ).all()
    for ord_req in open_orders:
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
                    name=item_name, item_code=gen_code, current_stock=quantity,
                    price=price, supplier=vendor, storage_site=site, uom=uom, minimum_stock=0
                )
                db.add(new_item)
                db.flush()
                db.add(models.Transaction(item_id=new_item.id, type="IN", quantity=quantity, user_id=current_user.id, total_value=float(quantity * price)))
                db.add(models.GRNRecord(item_id=new_item.id, quantity=quantity, uom=uom,
                    received_by=current_user.full_name or current_user.username,
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

                item.current_stock += quantity
                db.add(models.Transaction(item_id=item.id, type="IN", quantity=quantity, user_id=current_user.id, total_value=float(quantity * item.price)))
                db.add(models.GRNRecord(item_id=item.id, quantity=quantity, uom=uom,
                    received_by=current_user.full_name or current_user.username,
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
        ts = g.timestamp.strftime("%d-%m-%Y %H:%M") if g.timestamp else ""
        item_name = g.item.name if g.item else "Unknown Item"
        item_code = g.item.item_code if g.item else "—"
        uploader = g.uploader.username if g.uploader else "System"
        rows += f"""
        <tr class="border-b hover:bg-slate-50 text-xs">
            <td class="p-3 text-slate-500 font-mono">{ts}</td>
            <td class="p-3 font-semibold text-slate-800">{item_name}</td>
            <td class="p-3 font-mono text-slate-500">{item_code}</td>
            <td class="p-3 text-center font-mono font-bold text-slate-700">{g.quantity} {g.uom}</td>
            <td class="p-3 text-slate-500">{uploader}</td>
            <td class="p-3 text-right">
                <a href="/grn/download/{g.id}" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all">⬇ Download</a>
            </td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>GRN Downloads - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{{font-family:'Inter',sans-serif;}}</style>
</head>
<body class="bg-slate-50 min-h-screen p-8">
    <div class="max-w-5xl mx-auto">
        <div class="flex items-center justify-between mb-6">
            <div>
                <a href="/" class="text-indigo-600 text-xs font-bold hover:underline">&#8592; Back to Dashboard</a>
                <h1 class="text-xl font-black text-slate-900 mt-1">&#128196; GRN Download Centre</h1>
                <p class="text-xs text-slate-400 mt-0.5">Goods Received Notes — uploaded inward transaction records</p>
            </div>
            <a href="/mis/list" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs px-4 py-2 rounded-lg transition-all border border-indigo-200">&#128203; MIS Download Centre</a>
        </div>
        <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase text-xs border-b border-slate-200">
                        <th class="p-4">Timestamp</th>
                        <th class="p-4">Item Name</th>
                        <th class="p-4">Item Code</th>
                        <th class="p-4 text-center">Qty / UOM</th>
                        <th class="p-4">Uploaded By</th>
                        <th class="p-4 text-right pr-5">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">{rows if rows else '<tr><td colspan="6" class="p-8 text-center text-slate-400 text-sm">No GRNs uploaded yet.</td></tr>'}</tbody>
            </table>
        </div>
    </div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/grn/download/{grn_id}")
def grn_download(grn_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import os
    from fastapi.responses import FileResponse
    grn = db.query(models.GRNRecord).filter(models.GRNRecord.id == grn_id).first()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    grn_path = os.path.join("grn_uploads", grn.grn_filename)
    if not os.path.exists(grn_path):
        raise HTTPException(status_code=404, detail="GRN file missing from server")
    return FileResponse(path=grn_path, filename=grn.grn_filename, media_type="application/octet-stream")


@app.get("/mis/list", response_class=HTMLResponse)
def mis_list(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    assignments = db.query(models.MaterialAssignment).filter(
        models.MaterialAssignment.mis_filename != None
    ).order_by(models.MaterialAssignment.timestamp.desc()).all()
    rows = ""
    for a in assignments:
        ts = a.timestamp.strftime("%d-%m-%Y %H:%M") if a.timestamp else ""
        item_name = a.item.name if a.item else "Unknown Item"
        item_code = a.item.item_code if a.item else "—"
        dept = getattr(a, 'department', '—') or '—'
        rows += f"""
        <tr class="border-b hover:bg-slate-50 text-xs">
            <td class="p-3 text-slate-500 font-mono">{ts}</td>
            <td class="p-3 font-semibold text-slate-800">{item_name}</td>
            <td class="p-3 font-mono text-slate-500">{item_code}</td>
            <td class="p-3 text-center font-mono font-bold text-slate-700">{a.quantity} {a.uom}</td>
            <td class="p-3 text-slate-700 font-medium">{a.issued_to}</td>
            <td class="p-3 text-slate-500">{dept}</td>
            <td class="p-3 text-right">
                <a href="/mis/download/{a.id}" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all">⬇ Download MIS</a>
            </td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>MIS Download Centre - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{{font-family:'Inter',sans-serif;}}</style>
</head>
<body class="bg-slate-50 min-h-screen p-8">
    <div class="max-w-5xl mx-auto">
        <div class="flex items-center justify-between mb-6">
            <div>
                <a href="/" class="text-indigo-600 text-xs font-bold hover:underline">&#8592; Back to Dashboard</a>
                <h1 class="text-xl font-black text-slate-900 mt-1">&#128203; MIS Download Centre</h1>
                <p class="text-xs text-slate-400 mt-0.5">Material Issue Slips — uploaded issuance records</p>
            </div>
            <a href="/grn/list" class="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs px-4 py-2 rounded-lg transition-all border border-slate-200">&#128196; GRN Download Centre</a>
        </div>
        <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase text-xs border-b border-slate-200">
                        <th class="p-4">Timestamp</th>
                        <th class="p-4">Item Name</th>
                        <th class="p-4">Item Code</th>
                        <th class="p-4 text-center">Qty / UOM</th>
                        <th class="p-4">Issued To</th>
                        <th class="p-4">Department</th>
                        <th class="p-4 text-right pr-5">Action</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">{rows if rows else '<tr><td colspan="7" class="p-8 text-center text-slate-400 text-sm">No MIS records uploaded yet.</td></tr>'}</tbody>
            </table>
        </div>
    </div>
</body></html>"""
    return HTMLResponse(html)


@app.get("/mis/download/{assignment_id}")
def mis_download(assignment_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)
    import os
    from fastapi.responses import FileResponse
    a = db.query(models.MaterialAssignment).filter(models.MaterialAssignment.id == assignment_id).first()
    if not a or not a.mis_filename:
        raise HTTPException(status_code=404, detail="MIS not found")
    mis_path = os.path.join("mis_uploads", a.mis_filename)
    if not os.path.exists(mis_path):
        raise HTTPException(status_code=404, detail="MIS file missing from server")
    return FileResponse(path=mis_path, filename=a.mis_filename, media_type="application/octet-stream")


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
    initial_stock: int = Form(0),  # Fixed signature mapping to HTML key
    minimum_stock: int = Form(0),
    db: Session = Depends(get_db)
):
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
            user_id=1,
            total_value=float(initial_stock * item_unit_price)
        )
        db.add(initial_transaction)

    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/items/edit/{item_id}")
def edit_item(
    item_id: int,
    name: str = Form(...),
    item_code: str = Form(...),  # Explicitly accept the form field data
    current_stock: int = Form(...),
    minimum_stock: int = Form(...),
    price: float = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if current_user.role != "Admin":
        return HTMLResponse("<html><body><h2>Access Denied: Admin privileges required</h2></body></html>", status_code=403)
        
    # Changed models.InventoryItem to models.Item to match your schema definitions
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
    db_item.current_stock = current_stock
    db_item.minimum_stock = minimum_stock
    db_item.price = price
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/items/delete/{item_id}")
def delete_item(item_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Access Denied", status_code=403)
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
        item.current_stock = int(new_stock)
        db.commit()
        
    return RedirectResponse(url="/", status_code=303)


@app.post("/material/issue")
async def issue_materials(
    item_id: int = Form(...),
    quantity: int = Form(...),
    uom: str = Form(...),
    issued_to: str = Form(...),
    issued_by: str = Form(...),
    department: str = Form("General Operations"),
    remarks: str = Form(None),
    mis_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    # MIS upload is mandatory to proceed
    if not mis_file or not mis_file.filename:
        return HTMLResponse("<script>alert('MIS (Material Issue Slip) upload is mandatory before recording an issue.'); window.history.back();</script>")

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item or item.current_stock < quantity:
        return RedirectResponse(url="/?error=insufficient_stock", status_code=303)

    # Save MIS file to disk
    import os, datetime as dt
    mis_dir = "mis_uploads"
    os.makedirs(mis_dir, exist_ok=True)
    timestamp_str = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"MIS_{item.item_code}_{timestamp_str}_{mis_file.filename.replace(' ', '_')}"
    mis_path = os.path.join(mis_dir, safe_filename)
    contents = await mis_file.read()
    with open(mis_path, "wb") as f:
        f.write(contents)

    item.current_stock -= quantity

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
        mis_uploaded_by_id=current_user.id,
        mis_upload_timestamp=now,
        timestamp=now
    )
    db.add(new_assignment)
    db.commit()
    return RedirectResponse(url="/?tab=allocations", status_code=303)


@app.post("/procurement/request")
def create_procurement_request(
    item_id: str = Form(...),
    quantity: int = Form(...),
    department: str = Form(...),
    new_item_name: str = Form(None),
    detailed_specification: str = Form(None),
    db: Session = Depends(get_db),
    user_str: str = Cookie(None, alias="session_user")
):
    if not user_str:
        return RedirectResponse(url="/login", status_code=303)
    
    current_user = db.query(models.User).filter(models.User.username == user_str).first()
    
    new_request = models.ProcurementRequest(
        quantity=quantity,
        department=department.strip(),
        requested_by_id=current_user.id,
        status="Pending"
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


@app.post("/procurement/order/{req_id}")
def place_order(req_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user or current_user.role != "Admin":
        return HTMLResponse("Unauthorized", status_code=403)
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if req and req.status == "Order Pending":
        req.status = "Order Placed"
        db.commit()
    return RedirectResponse(url="/", status_code=303)


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
                    category="Procured Items",
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


@app.get("/procurement/delete/{request_id}")
def delete_procurement_request(
    request_id: int,
    session_user: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)
        
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


def build_sidebar(current_user) -> str:
    """Returns the persistent left sidebar HTML for standalone pages."""
    import html as _html
    role_initial = (current_user.role or "S")[0].upper()
    return f"""
    <aside class="w-64 bg-white border-r border-slate-200 flex flex-col shrink-0 shadow-sm z-20 min-h-screen sticky top-0">
        <div class="p-5 border-b border-slate-100 text-center">
            <img src="/static/logo.png" alt="EIPL Logo" class="h-16 mx-auto mb-2 object-contain"
                onerror="this.style.display='none';document.getElementById('sbLogoFallback').style.display='inline-block';">
            <div id="sbLogoFallback" style="display:none;" class="bg-indigo-600 px-3 py-2 rounded-xl text-white font-black text-sm mb-2">EIPL</div>
            <h2 class="font-black text-slate-900 tracking-tight text-[13px] leading-tight uppercase">Electra Infracon Pvt Ltd</h2>
            <p class="text-[10px] text-slate-400 font-mono mt-1">{_html.escape(current_user.username)}</p>
        </div>
        <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
            <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2">Core Dashboard</p>
            <a href="/material-movement" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all group">
                <i class="fa-solid fa-truck-ramp-box w-5 text-center text-slate-400 group-hover:text-emerald-600"></i> Material Movement
            </a>
            <a href="/inventory/summary" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all group">
                <i class="fa-solid fa-chart-bar w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Material Flow Dashboard
            </a>
            <a href="/" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all group">
                <i class="fa-solid fa-boxes-stacked w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Inventory Configuration
            </a>
            <a href="/?tab=requisitions" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all group">
                <i class="fa-solid fa-file-invoice-dollar w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Requisitions
            </a>
            <a href="/?tab=allocations" class="w-full flex items-center gap-3 px-3 py-2.5 text-slate-600 hover:bg-slate-50 hover:text-slate-900 rounded-xl text-sm font-medium transition-all group">
                <i class="fa-solid fa-list-check w-5 text-center text-slate-400 group-hover:text-indigo-600"></i> Allocations
            </a>
            <div class="pt-4 mt-4 border-t border-slate-100 space-y-1">
                <p class="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2">Administration</p>
                <a href="/?open=employee" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-all group">
                    <i class="fa-solid fa-user-plus w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> Employee Registry
                </a>
                <a href="/?open=access" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-all group">
                    <i class="fa-solid fa-key w-4 text-center text-slate-400 group-hover:text-emerald-600"></i> Grant User Access
                </a>
                <a href="/grn/list" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-all group">
                    <i class="fa-solid fa-download w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> GRN Download Centre
                </a>
                <a href="/mis/list" class="w-full flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-all group">
                    <i class="fa-solid fa-file-arrow-down w-4 text-center text-slate-400 group-hover:text-indigo-600"></i> MIS Download Centre
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


@app.get("/inventory/summary", response_class=HTMLResponse)
def inventory_summary(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    items = db.query(models.Item).all()
    transactions = db.query(models.Transaction).all()
    assignments = db.query(models.MaterialAssignment).all()
    grns = db.query(models.GRNRecord).all()

    import json as _json, html as _html

    # Build transaction log per item
    txn_map = {}
    for t in transactions:
        if t.item_id not in txn_map:
            txn_map[t.item_id] = []
        txn_map[t.item_id].append({
            "date": t.timestamp.strftime("%d-%m-%Y %H:%M") if t.timestamp else "",
            "type": t.type,
            "qty": t.quantity,
            "uom": "—",
            "person": "—",
            "direction": "IN" if t.type in ("IN","IN_PO") else "OUT"
        })

    # Build a price lookup from IN transactions: item_id -> {date_str: per_unit_price}
    txn_price_lookup = {}
    for t in transactions:
        if t.type == "IN" and t.quantity and t.quantity > 0 and t.total_value:
            per_unit = round(t.total_value / t.quantity, 2)
            ts_str = t.timestamp.strftime("%d-%m-%Y %H:%M") if t.timestamp else ""
            if t.item_id not in txn_price_lookup:
                txn_price_lookup[t.item_id] = {}
            txn_price_lookup[t.item_id][ts_str] = per_unit

    # Overlay GRN data onto IN transactions with price/vendor info
    grn_map = {}
    for g in grns:
        grn_map[g.item_id] = grn_map.get(g.item_id, [])
        item_obj = next((i for i in items if i.id == g.item_id), None)
        catalog_price = item_obj.price if item_obj else 0.0
        catalog_vendor = item_obj.supplier if item_obj else "—"
        grn_date = g.timestamp.strftime("%d-%m-%Y %H:%M") if g.timestamp else ""
        # Match the per-unit price from the transaction recorded at same timestamp
        entry_price = txn_price_lookup.get(g.item_id, {}).get(grn_date, catalog_price)
        price_diff = round(entry_price - catalog_price, 2) if abs(entry_price - catalog_price) > 0.01 else None
        grn_map[g.item_id].append({
            "date": grn_date,
            "type": "IN",
            "qty": g.quantity,
            "uom": g.uom or "Nos",
            "person": getattr(g, 'received_by', '') or (g.uploader.username if g.uploader else "—"),
            "direction": "IN",
            "vendor": catalog_vendor,
            "price": entry_price,
            "price_diff": price_diff
        })

    # Overlay material assignments (OUT)
    for a in assignments:
        if a.item_id not in txn_map:
            txn_map[a.item_id] = []
        txn_map[a.item_id].append({
            "date": a.timestamp.strftime("%d-%m-%Y %H:%M") if a.timestamp else "",
            "type": "OUT",
            "qty": a.quantity,
            "uom": a.uom or "Nos",
            "person": a.issued_to or "—",
            "direction": "OUT"
        })

    rows_html = ""
    is_admin = current_user.role == "Admin"
    for it in items:
        item_cat = getattr(it, 'category', '—')
        item_sup = getattr(it, 'supplier', '—')
        low_badge = ' <span class="text-rose-500 font-black text-[9px] animate-pulse">LOW</span>' if it.current_stock <= it.minimum_stock else ""

        # Build txn log: merge GRN entries + assignments, sort by date desc
        all_txns = grn_map.get(it.id, []) + [t for t in txn_map.get(it.id, []) if t["direction"] == "OUT"]
        all_txns.sort(key=lambda x: x["date"], reverse=True)

        txn_rows = ""
        for tx in all_txns:
            color = "text-emerald-600 bg-emerald-50" if tx["direction"] == "IN" else "text-rose-600 bg-rose-50"
            person_label = f"<span class='text-slate-500'>Recv: {_html.escape(tx['person'])}</span>" if tx["direction"] == "IN" else f"<span class='text-slate-500'>Issued: {_html.escape(tx['person'])}</span>"
            txn_rows += f"""<tr class='border-b border-slate-100 text-[11px]'>
                <td class='px-3 py-2 font-mono text-slate-400'>{tx['date']}</td>
                <td class='px-3 py-2'><span class='font-bold px-1.5 py-0.5 rounded {color}'>{tx['type']}</span></td>
                <td class='px-3 py-2 font-mono font-bold'>{tx['qty']}</td>
                <td class='px-3 py-2 text-slate-500'>{tx['uom']}</td>
                <td class='px-3 py-2'>{person_label}</td>
            </tr>"""

        if not txn_rows:
            txn_rows = "<tr><td colspan='5' class='px-3 py-4 text-center text-slate-400 text-[11px]'>No transactions recorded.</td></tr>"

        txn_json = _json.dumps(all_txns)
        safe_name = _html.escape(it.name)
        safe_code = _html.escape(it.item_code)

        admin_cols = f"""<td class="p-3 text-slate-600 text-[11px]">{item_sup}</td>
            <td class="p-3 font-mono text-slate-700">&#8377;{it.price:,.2f}</td>""" if is_admin else ""

        rows_html += f"""<tr class="border-b border-slate-100 hover:bg-slate-50/50 text-xs" data-name="{safe_name.lower()}" data-code="{safe_code.lower()}" data-supplier="{_html.escape(item_sup).lower()}">
            <td class="p-3 font-semibold text-slate-900">{safe_name}{low_badge}<div class="text-[10px] text-slate-400">{item_cat}</div></td>
            <td class="p-3 font-mono text-slate-500 text-[11px]">{safe_code}</td>
            {admin_cols}
            <td class="p-3 font-mono font-bold text-center {'text-rose-600' if it.current_stock <= it.minimum_stock else 'text-slate-900'}">{it.current_stock}</td>
            <td class="p-3 font-mono text-center text-slate-400">{it.minimum_stock}</td>
            <td class="p-3 text-center">
                <button onclick="openTxnLog({it.id}, '{safe_name}', '{safe_code}')"
                    class="bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold text-[10px] px-2.5 py-1.5 rounded-lg transition-all flex items-center gap-1 mx-auto">
                    <i class="fa-solid fa-book-open text-[9px]"></i> Log
                </button>
            </td>
        </tr>
        <script>window.__txnData = window.__txnData||{{}};window.__txnData[{it.id}]={txn_json};</script>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><title>Material Flow Dashboard - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{{font-family:'Inter',sans-serif;}}
.modal-bg{{position:fixed;inset:0;background:rgba(15,23,42,0.5);backdrop-filter:blur(4px);display:flex;align-items:center;justify-content:center;z-index:999;}}
</style>
</head>
<body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user)}
<div class="flex-1 flex flex-col min-h-screen overflow-x-hidden">
<div class="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
    <div class="flex items-center gap-3">
        <h1 class="text-sm font-black text-slate-900 uppercase tracking-wider"><i class="fa-solid fa-chart-bar text-indigo-600 mr-1"></i> Material Flow Dashboard</h1>
    </div>
    <div class="flex items-center gap-2">
        <div class="relative">
            <i class="fa-solid fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-[10px]"></i>
            <input type="text" id="summarySearch" placeholder="Search items..." oninput="filterSummary()"
                class="pl-7 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:border-indigo-400 w-48">
        </div>
        <select id="summaryPageSize" onchange="renderPage()" class="bg-slate-50 border border-slate-200 text-xs px-2.5 py-2 rounded-xl">
            <option value="15">15 / page</option>
            <option value="50">50 / page</option>
            <option value="100">100 / page</option>
        </select>
        <select id="stockFilter" onchange="filterSummary()" class="bg-slate-50 border border-slate-200 text-xs px-2.5 py-2 rounded-xl">
            <option value="">All Stock</option>
            <option value="low">Low Stock Only</option>
            <option value="ok">Adequate Stock</option>
        </select>
    </div>
</div>

<div class="max-w-[1400px] mx-auto p-6">
    <div class="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        <table class="w-full text-left border-collapse" id="summaryTable">
            <thead>
                <tr class="bg-slate-50 text-slate-500 font-semibold tracking-wider uppercase text-xs border-b border-slate-200">
                    <th class="p-4 pl-5 cursor-pointer hover:text-indigo-600" onclick="sortSummary(0)">Item Name <i class="fa-solid fa-sort text-[9px]"></i></th>
                    <th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortSummary(1)">Item Code <i class="fa-solid fa-sort text-[9px]"></i></th>
                    {'<th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortSummary(2)">Vendor <i class="fa-solid fa-sort text-[9px]"></i></th><th class="p-4 cursor-pointer hover:text-indigo-600" onclick="sortSummary(3)">Price <i class="fa-solid fa-sort text-[9px]"></i></th>' if is_admin else ''}
                    <th class="p-4 text-center cursor-pointer hover:text-indigo-600" onclick="sortSummary({'4' if is_admin else '2'})">Current Stock <i class="fa-solid fa-sort text-[9px]"></i></th>
                    <th class="p-4 text-center cursor-pointer hover:text-indigo-600" onclick="sortSummary({'5' if is_admin else '3'})">Safety Stock <i class="fa-solid fa-sort text-[9px]"></i></th>
                    <th class="p-4 text-center">Transaction Log</th>
                </tr>
            </thead>
            <tbody id="summaryBody">{rows_html}</tbody>
        </table>
        <div class="flex items-center justify-between px-5 py-3 border-t border-slate-100 bg-slate-50/50 text-xs text-slate-500">
            <span id="summaryInfo"></span>
            <div id="summaryPagination" class="flex items-center gap-1"></div>
        </div>
    </div>
</div>

<!-- Transaction Log Modal -->
<div id="txnModal" class="modal-bg hidden">
    <div class="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-3xl mx-4 flex flex-col max-h-[80vh]">
        <div class="flex items-center justify-between p-5 border-b border-slate-100">
            <div>
                <h3 class="text-sm font-black text-slate-900" id="txnModalTitle">Transaction Log</h3>
                <p class="text-[10px] text-slate-400 mt-0.5" id="txnModalSubtitle"></p>
            </div>
            <button onclick="closeTxnLog()" class="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-all">
                <i class="fa-solid fa-xmark text-sm"></i>
            </button>
        </div>
        <div class="overflow-y-auto flex-1">
            <table class="w-full text-left border-collapse text-xs">
                <thead class="sticky top-0">
                    <tr class="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-200">
                        <th class="px-4 py-3">Date</th>
                        <th class="px-4 py-3">Type</th>
                        <th class="px-4 py-3 text-center">Quantity</th>
                        <th class="px-4 py-3">UOM</th>
                        <th class="px-4 py-3">Person</th>
                        {'<th class="px-4 py-3">Vendor</th><th class="px-4 py-3">Rate &#8377;</th><th class="px-4 py-3">Price Diff</th>' if is_admin else ''}
                    </tr>
                </thead>
                <tbody id="txnLogBody"></tbody>
            </table>
        </div>
        <div class="p-4 border-t border-slate-100 flex justify-end">
            <button onclick="closeTxnLog()" class="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs px-4 py-2 rounded-xl transition-all">Close</button>
        </div>
    </div>
</div>

<script>
var allRows = Array.from(document.querySelectorAll('#summaryBody tr[data-name]'));
var filtered = allRows;
var currentPage = 1;
var sortCol = -1, sortDir = 1;
var IS_ADMIN = {'true' if is_admin else 'false'};

function filterSummary() {{
    var q = document.getElementById('summarySearch').value.toLowerCase();
    var sf = document.getElementById('stockFilter').value;
    filtered = allRows.filter(function(r) {{
        var matchText = !q || r.dataset.name.includes(q) || r.dataset.code.includes(q) || r.dataset.supplier.includes(q);
        var stocks = r.querySelectorAll('td');
        var cur = parseInt(stocks[4] ? stocks[4].textContent : '0') || 0;
        var safe = parseInt(stocks[5] ? stocks[5].textContent : '0') || 0;
        var matchStock = !sf || (sf === 'low' ? cur <= safe : cur > safe);
        return matchText && matchStock;
    }});
    currentPage = 1;
    renderPage();
}}

function renderPage() {{
    var ps = parseInt(document.getElementById('summaryPageSize').value) || 15;
    var total = filtered.length;
    var pages = Math.max(1, Math.ceil(total / ps));
    if (currentPage > pages) currentPage = pages;
    var start = (currentPage - 1) * ps;
    var end = Math.min(start + ps, total);
    allRows.forEach(function(r) {{ r.style.display = 'none'; }});
    document.querySelectorAll('#summaryBody script').forEach(function(s) {{ s.style.display = 'none'; }});
    for (var i = start; i < end; i++) {{ filtered[i].style.display = ''; }}
    document.getElementById('summaryInfo').textContent = 'Showing ' + (start+1) + '-' + end + ' of ' + total + ' items';
    var pb = document.getElementById('summaryPagination');
    pb.innerHTML = '';
    for (var p = 1; p <= pages; p++) {{
        var btn = document.createElement('button');
        btn.textContent = p;
        btn.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition-all ' + (p === currentPage ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-indigo-50 hover:text-indigo-600');
        btn.onclick = (function(pg) {{ return function() {{ currentPage = pg; renderPage(); }}; }})(p);
        pb.appendChild(btn);
    }}
}}

function sortSummary(col) {{
    if (sortCol === col) sortDir = -sortDir; else {{ sortCol = col; sortDir = 1; }}
    filtered.sort(function(a, b) {{
        var at = a.querySelectorAll('td')[col] ? a.querySelectorAll('td')[col].textContent.trim() : '';
        var bt = b.querySelectorAll('td')[col] ? b.querySelectorAll('td')[col].textContent.trim() : '';
        var an = parseFloat(at.replace(/[^0-9.-]/g,'')), bn = parseFloat(bt.replace(/[^0-9.-]/g,''));
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * sortDir;
        return at.localeCompare(bt) * sortDir;
    }});
    renderPage();
}}

function openTxnLog(itemId, name, code) {{
    document.getElementById('txnModalTitle').textContent = name + ' \u2014 Transaction Log';
    document.getElementById('txnModalSubtitle').textContent = 'Code: ' + code;
    var data = (window.__txnData && window.__txnData[itemId]) || [];
    var tbody = document.getElementById('txnLogBody');
    var colSpan = IS_ADMIN ? 8 : 5;
    if (!data.length) {{
        tbody.innerHTML = '<tr><td colspan="' + colSpan + '" class="px-4 py-6 text-center text-slate-400">No transactions found.</td></tr>';
    }} else {{
        tbody.innerHTML = data.map(function(tx) {{
            var color = tx.direction === 'IN' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700';
            var label = tx.direction === 'IN' ? 'Received by: ' : 'Issued to: ';
            var adminCols = '';
            if (IS_ADMIN && tx.direction === 'IN') {{
                var priceStr = tx.price != null ? '\u20b9' + Number(tx.price).toFixed(2) : '\u2014';
                var diffStr = '\u2014';
                var diffClass = '';
                if (tx.price_diff != null && tx.price_diff !== 0) {{
                    var sign = tx.price_diff > 0 ? '+' : '';
                    diffStr = sign + '\u20b9' + Number(tx.price_diff).toFixed(2);
                    diffClass = tx.price_diff > 0 ? 'text-rose-600 font-bold' : 'text-emerald-600 font-bold';
                }}
                adminCols = '<td class="px-4 py-2.5 text-slate-500 text-[11px]">' + (tx.vendor || '\u2014') + '</td>' +
                    '<td class="px-4 py-2.5 font-mono text-slate-700">' + priceStr + '</td>' +
                    '<td class="px-4 py-2.5 font-mono ' + diffClass + '">' + diffStr + '</td>';
            }} else if (IS_ADMIN) {{
                adminCols = '<td class="px-4 py-2.5 text-slate-300">\u2014</td><td class="px-4 py-2.5 text-slate-300">\u2014</td><td class="px-4 py-2.5 text-slate-300">\u2014</td>';
            }}
            return '<tr class="border-b border-slate-100 hover:bg-slate-50">' +
                '<td class="px-4 py-2.5 font-mono text-slate-400 text-[11px]">' + tx.date + '</td>' +
                '<td class="px-4 py-2.5"><span class="font-bold px-2 py-0.5 rounded text-[11px] ' + color + '">' + tx.type + '</span></td>' +
                '<td class="px-4 py-2.5 font-mono font-bold text-center">' + tx.qty + '</td>' +
                '<td class="px-4 py-2.5 text-slate-500">' + tx.uom + '</td>' +
                '<td class="px-4 py-2.5 text-slate-600 text-[11px]">' + label + '<b>' + tx.person + '</b></td>' +
                adminCols +
            '</tr>';
        }}).join('');
    }}
    document.getElementById('txnModal').classList.remove('hidden');
}}

function closeTxnLog() {{
    document.getElementById('txnModal').classList.add('hidden');
}}

document.getElementById('txnModal').addEventListener('click', function(e) {{
    if (e.target === this) closeTxnLog();
}});

renderPage();
</script>
</div><!-- end flex-1 -->
</body></html>"""
    return HTMLResponse(html)


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

            item.current_stock -= quantity
            db.add(models.MaterialAssignment(
                item_id=item.id,
                quantity=quantity,
                uom=uom or (item.uom or "Nos"),
                issued_to=issued_to,
                issued_by=current_user.full_name or current_user.username,
                department=department,
                remarks=remarks,
                custodian=issued_to,
                timestamp=_dt.datetime.utcnow()
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
    inv_json = _json.dumps([{"id": i.id, "name": i.name, "code": i.item_code, "stock": i.current_stock,
        "uom": getattr(i,'uom',None) or "", "price": i.price or 0.0, "vendor": getattr(i,'supplier','') or ""} for i in items])
    emp_opts = "".join([f'<option value="{_html.escape(e.name)}">{_html.escape(e.name)} ({e.role_title})</option>' for e in employees])
    recv = _html.escape(current_user.full_name or current_user.username)
    html_page = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><title>Material Movement - EIPL</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>body{{font-family:'Inter',sans-serif;}}</style>
</head><body class="bg-slate-50 min-h-screen flex">
{build_sidebar(current_user)}
<div class="flex-1 flex flex-col min-h-screen overflow-x-hidden">
<div class="bg-white border-b border-slate-200 px-8 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
    <div class="flex items-center gap-3">
        <h1 class="text-sm font-black text-slate-900 uppercase tracking-wider"><i class="fa-solid fa-truck-ramp-box text-indigo-600 mr-1"></i> Material Movement</h1>
    </div>
    <span class="text-[11px] text-slate-400 font-mono">{_html.escape(current_user.username)} ({current_user.role})</span>
</div>
<div class="max-w-[1400px] mx-auto p-6">
  <div class="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">

  <!-- LEFT: INWARD -->
  <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
    <div class="flex items-center justify-between px-5 py-3 border-b-2 border-emerald-400 bg-emerald-50/60">
      <div>
        <div class="flex items-center gap-2 mb-0.5">
          <span class="bg-emerald-500 text-white text-[10px] font-black px-2 py-0.5 rounded tracking-widest uppercase">Inward</span>
          <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase">&#8595; Inward Transaction / Add to Catalog</h2>
        </div>
        <p class="text-[10px] text-slate-400">Search existing item or register new — GRN mandatory</p>
      </div>
      <a href="/inward/bulk-template" class="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 px-2 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1 whitespace-nowrap"><i class="fa-solid fa-download"></i> Template</a>
    </div>
    <form action="/transaction" method="POST" enctype="multipart/form-data" class="p-5 space-y-3 text-xs text-slate-700">
      <div>
        <label class="block font-semibold text-slate-600 mb-1">Search &amp; Select Item <span class="text-slate-400 font-normal">or add new below</span></label>
        <div class="relative">
          <input type="text" id="inward_item_search" placeholder="Type item name or code..." autocomplete="off"
            class="w-full bg-slate-50 border border-slate-200 text-slate-900 p-2.5 rounded-xl focus:outline-none focus:border-emerald-500 focus:bg-white shadow-sm text-xs"
            oninput="filterInwardItems(this.value)" onfocus="showInwardDropdown()">
          <div id="inward_item_dropdown" class="absolute z-30 w-full bg-white border border-slate-200 rounded-xl shadow-xl mt-1 max-h-48 overflow-y-auto hidden"></div>
        </div>
        <input type="hidden" id="inward_item_id" name="item_id" value="NEW_INWARD_ITEM">
        <p id="inward_selected_label" class="text-[10px] text-amber-600 font-semibold mt-1">+ New item — fill details below</p>
      </div>
      <div id="inward_new_item_fields" class="bg-amber-50/40 border border-amber-200/60 rounded-xl p-3 space-y-2.5">
        <p class="text-[10px] font-bold text-amber-700 uppercase tracking-wider">New Item Details</p>
        <div class="grid grid-cols-2 gap-2">
          <div><label class="block font-semibold text-slate-500 mb-1">Item Name <span class="text-rose-500">*</span></label>
            <input type="text" name="new_item_name" placeholder="e.g. Steel Pipe" class="w-full bg-white border border-slate-200 p-2 rounded-lg text-xs focus:outline-none focus:border-indigo-500"></div>
          <div><label class="block font-semibold text-slate-500 mb-1">Item Code <span class="text-rose-500">*</span></label>
            <input type="text" name="new_item_code" placeholder="e.g. EIPL-ST-05" class="w-full bg-white border border-slate-200 p-2 rounded-lg font-mono uppercase text-xs focus:outline-none focus:border-indigo-500" oninput="this.value=this.value.toUpperCase()"></div>
        </div>
        <input type="text" name="site" placeholder="Storage Site e.g. Udaipur Yard" class="w-full bg-white border border-slate-200 p-2 rounded-lg text-xs focus:outline-none focus:border-indigo-500">
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
        <div><label class="block font-semibold text-slate-500 mb-1">Vendor / Supplier</label>
          <input type="text" name="vendor" placeholder="Supplier name" class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg text-xs"></div>
        <div><label class="block font-semibold text-slate-500 mb-1">Rate &#8377;</label>
          <input type="number" step="0.01" name="price" placeholder="0.00" class="w-full bg-slate-50 border border-slate-200 p-2 rounded-lg font-mono text-xs"></div>
      </div>
      <div class="bg-indigo-50/60 border border-indigo-100 rounded-lg p-2 text-[11px] text-indigo-700 font-medium">
        <i class="fa-solid fa-user-check mr-1"></i> Received By: <span class="font-black">{recv} ({_html.escape(current_user.username)})</span>
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
      <div class="flex items-center gap-2 mb-0.5">
        <span class="bg-rose-500 text-white text-[10px] font-black px-2 py-0.5 rounded tracking-widest uppercase">Outward</span>
        <h2 class="text-xs font-black tracking-wider text-slate-800 uppercase">&#8593; Material Issue Slip</h2>
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
      <div class="flex items-center justify-between mb-2">
        <label class="block font-black text-[10px] uppercase text-rose-700 tracking-wider">&#128202; Bulk MIS Import (CSV)</label>
        <a href="/mis/bulk-template" class="bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-2 py-1 rounded-lg text-[10px] font-bold flex items-center gap-1"><i class="fa-solid fa-download"></i> Template</a>
      </div>
      <form action="/mis/bulk-import" method="POST" enctype="multipart/form-data" class="flex gap-2">
        <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border border-slate-200 text-slate-600 text-[10px] p-2 rounded-xl">
        <button type="submit" class="bg-rose-600 text-white px-3 py-2 rounded-xl font-bold text-[10px] shrink-0">Import</button>
      </form>
      <p class="text-[10px] text-slate-400 mt-1">Columns: item_code, quantity, uom, issued_to, department, remarks</p>
    </div>
  </div>

  </div><!-- end grid -->
</div>

<script id="mm-inv" type="application/json">{inv_json}</script>
<script>
var MMINV = JSON.parse(document.getElementById('mm-inv').textContent);
function mkDd(items, cls) {{
    return items.slice(0,10).map(function(i) {{
        return '<div class="p-2.5 hover:bg-indigo-50 cursor-pointer border-b border-slate-100 last:border-0 ' + cls + '" data-id="'+i.id+'" data-name="'+i.name.replace(/"/g,"&quot;")+'" data-code="'+i.code+'" data-stock="'+i.stock+'" data-uom="'+i.uom+'" data-price="'+i.price+'" data-vendor="'+i.vendor+'">' +
        '<div class="font-semibold text-xs pointer-events-none">'+i.name+'</div>' +
        '<div class="text-[10px] text-slate-400 pointer-events-none">'+i.code+' | Stock: '+i.stock+'</div></div>';
    }}).join('') || '<div class="p-3 text-slate-400 text-xs">No items found</div>';
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
        document.getElementById('inward_item_id').value=el.dataset.id;
        document.getElementById('inward_item_search').value=el.dataset.name+' ('+el.dataset.code+')';
        document.getElementById('inward_selected_label').textContent='Selected: '+el.dataset.name+' | Stock: '+el.dataset.stock;
        document.getElementById('inward_selected_label').className='text-[10px] text-indigo-600 font-semibold mt-1';
        document.getElementById('inward_new_item_fields').style.display='none';
        document.getElementById('inward_item_dropdown').classList.add('hidden');
        if(el.dataset.uom)document.getElementById('inward_uom_select').value=el.dataset.uom;
        if(el.dataset.price)document.querySelector('[name=price]').value=el.dataset.price;
        if(el.dataset.vendor)document.querySelector('[name=vendor]').value=el.dataset.vendor;
        return;
    }}
    var el2=e.target.closest('.mis-item');
    if(el2){{
        document.getElementById('mis_item_id').value=el2.dataset.id;
        document.getElementById('mis_item_search').value=el2.dataset.name+' ('+el2.dataset.code+')';
        document.getElementById('mis_selected_label').textContent='Selected: '+el2.dataset.name+' | Stock: '+el2.dataset.stock;
        document.getElementById('mis_uom_display').value=el2.dataset.uom||'';
        document.getElementById('mis_item_dropdown').classList.add('hidden');
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
    window.openEditItemModal = function(id, name, Unique_code, price, current_stock, minimum_stock) {
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
        
        item_cat = getattr(it, 'category', 'Consumables')
        item_sup = getattr(it, 'supplier', 'EIPL Approved Vendor')
        item_site = getattr(it, 'storage_site', 'Store Yard')

        import html as _html
        h_name = _html.escape(it.name, quote=True)
        h_code = _html.escape(it.item_code, quote=True)
        h_vendor = _html.escape(item_sup, quote=True)
        h_uom = _html.escape(getattr(it, 'uom', '') or '', quote=True)

        if current_user.role == "Admin":
            admin_only_cells = f"""
            <td class="p-3 text-slate-600 text-[11px] font-medium">{item_sup}</td>
            <td class="p-3 font-mono text-slate-600">&#8377;{it.price:,.2f}</td>"""
            action_cell = f"""
            <td class="p-3">
                <div class="flex items-center gap-2">
                    <button type="button"
                        data-action="procure"
                        data-id="{it.id}" data-name="{h_name}" data-code="{h_code}"
                        data-price="{it.price}" data-uom="{h_uom}" data-vendor="{h_vendor}"
                        class="text-emerald-600 hover:underline font-bold text-[11px]">⬇ Inward</button>
                    <button type="button"
                        data-action="edit-item"
                        data-id="{it.id}" data-name="{h_name}" data-code="{h_code}"
                        data-price="{it.price}" data-stock="{it.current_stock}" data-minstock="{it.minimum_stock}"
                        class="text-amber-600 hover:underline font-bold text-[11px]">Edit</button>
                    <form action="/items/delete/{it.id}" method="POST" onsubmit="return confirm('Remove this item?');" class="inline m-0">
                        <button type="submit" class="text-rose-600 hover:underline font-bold text-[11px] bg-transparent border-none p-0 cursor-pointer inline">Delete</button>
                    </form>
                </div>
            </td>"""
        else:
            admin_only_cells = ""
            action_cell = f"""
            <td class="p-3">
                <button type="button"
                    data-action="procure"
                    data-id="{it.id}" data-name="{h_name}" data-code="{h_code}"
                    data-price="{it.price}" data-uom="{h_uom}" data-vendor="{h_vendor}"
                    class="text-emerald-600 hover:underline font-bold text-[11px]">⬇ Inward</button>
            </td>"""

        inventory_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/50" data-row="1">
            <td class="p-3 font-semibold text-slate-900">
                <span>{it.name}</span>{alert_status}
                <div class="text-[10px] text-slate-400 mt-0.5">
                    <span class="bg-slate-100 px-1 py-0.5 rounded text-slate-600">{item_cat}</span> 
                    &bull; <span class="bg-blue-50 px-1 py-0.5 rounded text-blue-600">{item_site}</span>
                </div>
            </td>
            <td class="p-3 font-mono text-[11px] text-slate-500">{it.item_code}</td>
            {admin_only_cells}
            <td class="p-3 font-mono font-bold text-slate-900" data-sort="{it.current_stock}">{it.current_stock}</td>
            <td class="p-3 font-mono text-slate-400" data-sort="{it.minimum_stock}">{it.minimum_stock}</td>
            {action_cell}
        </tr>
        """

    req_rows = ""
    reqs = db.query(models.ProcurementRequest).order_by(models.ProcurementRequest.timestamp.desc()).all()
    is_admin = current_user.role == "Admin"

    for r in reqs:
        date_str = r.timestamp.strftime("%d-%m %H:%M") if r.timestamp else ""

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
            if is_admin:
                order_btn = f"""<form action="/procurement/order/{r.id}" method="POST" class="inline"><input type="submit" value="Order" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-2 py-0.5 rounded cursor-pointer text-[10px]"></form>"""
                flow = f"""<div class="flex items-center gap-1 justify-center">{print_btn} {order_btn}</div>"""
            else:
                flow = f"""<div class="flex justify-center">{print_btn}</div>"""

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
            msg_time = msg.timestamp.strftime("%d-%m %H:%M") if msg.timestamp else ""
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

        req_rows += f"""<tr class="border-b hover:bg-slate-50 text-xs align-middle" data-row="1" data-text="{date_str} {r.requester.username if r.requester else ''} {r.status} {r.department or ''}">
            <td class="p-3 text-slate-500 font-mono whitespace-nowrap text-center">{date_str}</td>
            <td class="p-3 text-slate-800 text-center">{item_desc_display}</td>
            <td class="p-3 font-mono font-semibold text-center">{r.quantity}</td>
            {est_td}
            <td class="p-3 text-center">{code_cell}</td>
            <td class="p-3 text-center">{spec_cell}</td>
            <td class="p-3 text-slate-500 whitespace-nowrap text-center">{r.requester.username if r.requester else 'System'}</td>
            <td class="p-3 text-center" data-status="{r.status}">{badge}</td>
            <td class="p-3">{msg_thread_cell}</td>
            <td class="p-3 text-center">{flow}</td>
        </tr>"""


    assigned_rows = ""
    for a in assignments:
        ts = a.timestamp.strftime("%d-%m-%Y %H:%M") if a.timestamp else "—"
        item_name = a.item.name if a.item else 'Archived Asset'
        dept = getattr(a, 'department', '—') or '—'
        assigned_rows += f"""<tr class="border-b hover:bg-slate-50 text-xs" data-row="1">
            <td class="p-3 font-mono text-slate-400 text-[11px]">{ts}</td>
            <td class="p-3 font-bold text-slate-800">{item_name}</td>
            <td class="p-3 font-mono font-bold text-blue-700 text-center" data-sort="{a.quantity}">{a.quantity}</td>
            <td class="p-3 font-mono text-slate-500 text-center">{a.uom}</td>
            <td class="p-3 text-slate-700 font-medium">{a.issued_to}</td>
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
                    <form action='/employees/delete/{e.id}' method='POST' class='inline'><input type='submit' value='delete' class='text-rose-500 font-bold cursor-pointer hover:underline bg-transparent border-0 text-[10px]'></form>
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

        admin_panel = f"""
        <div class="bg-white border border-slate-200 rounded-2xl shadow-sm p-5 text-center mb-4">
            <i class="fa-solid fa-truck-ramp-box text-3xl text-emerald-500 mb-2"></i>
            <h3 class="font-black text-slate-800 text-sm mb-1">Material Movement</h3>
            <p class="text-[11px] text-slate-400 mb-3">Record inward &amp; outward material transactions</p>
            <a href="/material-movement" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs px-6 py-2.5 rounded-xl transition-all inline-block">Open Material Movement &#8594;</a>
        </div>
        """

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
                    <form action='/admin/users/delete/{u.id}' method='POST' class='inline'><input type='submit' value='delete' class='text-rose-500 font-bold cursor-pointer hover:underline bg-transparent border-0 text-[10px]'></form>
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
        .replace("__IS_ADMIN__", "true" if current_user.role == "Admin" else "false")