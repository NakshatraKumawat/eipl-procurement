import csv
import hashlib
from io import StringIO
from fastapi import FastAPI, Form, Depends, Cookie, Response, UploadFile, File
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


# -------------------------------------------------------------
# 1. FIXED EXPLICIT ROUTE FOR FAVICON TO BYPASS 404 EXCEPTIONS
# -------------------------------------------------------------
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Instantly returns an empty response so the browser stops searching,
    # which prevents a 404 exception from being thrown.
    return Response(status_code=204)


# -------------------------------------------------------------
# 2. FULLY FIXED ASYNC EXCEPTION HANDLER
# -------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    if exc.status_code == 404 and not request.cookies.get("session_user"):
        return RedirectResponse(url="/login", status_code=303)
    
    # Correctly await the async built-in handler to avoid the coroutine crash
    return await http_exception_handler(request, exc)


def hash_password(password: str) -> str:
    """Standardized SHA-256 password hashing for system security."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def run_structural_database_migrations():
    """Self-healing migration engine to clean up schema columns in existing databases."""
    db = SessionLocal()
    try:
        with engine.connect() as conn:
            # Check employees table
            inspector_emp = engine.dialect.get_columns(conn, "employees")
            existing_cols_emp = [col['name'] for col in inspector_emp]
            
            # Check procurement requests table
            inspector_proc = engine.dialect.get_columns(conn, "procurement_requests")
            existing_cols_proc = [col['name'] for col in inspector_proc]

        if "location" not in existing_cols_emp:
            db.execute(text("ALTER TABLE employees ADD COLUMN location TEXT DEFAULT 'Not Specified'"))
        if "contact" not in existing_cols_emp:
            db.execute(text("ALTER TABLE employees ADD COLUMN contact TEXT DEFAULT 'Not Specified'"))
            
        # Migrate procurement department structure safely 
        if "department" not in existing_cols_proc:
            db.execute(text("ALTER TABLE procurement_requests ADD COLUMN department TEXT DEFAULT 'Operations'"))
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Migration Adaptive Notice] Columns pre-aligned: {e}")
    finally:
        db.close()


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
def create_transaction(
    item_id: int = Form(...),
    type: str = Form(...),
    quantity: int = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        return HTMLResponse("<script>alert('Mutation Failed: Item not found.'); window.location='/';</script>")

    op_type = type.strip().upper()
    if op_type == "OUT":
        if item.current_stock < quantity:
            return HTMLResponse("<script>alert('Blocked: Insufficient warehouse stock level!'); window.location='/';</script>")
        item.current_stock -= quantity
    elif op_type == "IN":
        item.current_stock += quantity
    else:
        return HTMLResponse("<script>alert('Mutation Error: Invalid operations token.'); window.location='/';</script>")

    item_unit_price = item.price if item.price is not None else 0.0
    db.add(models.Transaction(
        item_id=item.id,
        type=op_type,
        quantity=quantity,
        user_id=current_user.id,
        total_value=float(quantity * item_unit_price)
    ))
    db.commit()
    return RedirectResponse(url="/", status_code=303)


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
            
        # --- SMART ENCODING FALLBACK MECHANISM ---
        try:
            decoded_content = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                decoded_content = contents.decode('cp1252')
            except UnicodeDecodeError:
                decoded_content = contents.decode('latin-1')

        # --- FIX: SPLIT LINES TO PREVENT NEWLINE ERRORS ---
        # Splitting by splitlines() handles all variations of \r, \n, and \r\n safely.
        clean_lines = decoded_content.splitlines()
        
        # --- DYNAMIC CSV DIALECT SNIFFER ---
        try:
            # Sniff using the first few lines instead of raw string slice
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
            
            # 👇 ADD THIS LINE TEMPORARILY FOR DEBUGGING 👇
            print(f"👉 RAW CSV ROW DATA: {dict(row)}")
    
            # Clean spaces from keys and values safely
            clean_row = {str(k).strip().lower(): str(v).strip() for k, v in row.items() if k is not None}

            # Example: Adding "product name" and "sku" if that's what your file uses
            name = clean_row.get("name") or clean_row.get("item name") or clean_row.get("product name")
            item_code = clean_row.get("item_code") or clean_row.get("code") or clean_row.get("sku")

            if not name or not item_code:
                print(f"[Bulk Import Warning] Skipping Row {row_index}: Missing structural 'name' or 'item_code'. Parsed headers look like: {list(clean_row.keys())}")
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
            description_text = f"{vendor} | Site: {site}" if site else vendor

            exists = db.query(models.Item).filter(models.Item.item_code == item_code).first()
            if exists:
                exists.name = name
                exists.current_stock = initial_stock
                exists.price = price
                exists.description = description_text
                updated_count += 1
            else:
                db.add(models.Item(
                    name=name,
                    item_code=item_code,
                    current_stock=initial_stock,
                    price=price,
                    description=description_text,
                    minimum_stock=5
                ))
                added_count += 1

        db.commit()
        return HTMLResponse(f"<script>alert('Bulk Process Complete! Added: {added_count}, Updated: {updated_count}'); window.location='/';</script>")
        
    except Exception as e:
        db.rollback()
        print(f"[Bulk Import Critical Exception]: {str(e)}")
        return HTMLResponse(f"<script>alert('Import processing error: {str(e)}'); window.location='/';</script>")


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


from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse

@app.post("/items/add")
def add_item(
    name: str = Form(...),
    item_code: str = Form(...),
    price: float = Form(0.0),
    current_stock: int = Form(0),  # Or initial_stock depending on what you used
    minimum_stock: int = Form(0),
    db: Session = Depends(get_db)
):
    # Check for duplicate item code
    existing_item = db.query(models.Item).filter(models.Item.item_code == item_code).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="Item code already exists!")

    # 1. Create the new item
    db_item = models.Item(
        name=name,
        item_code=item_code,
        price=price,
        current_stock=current_stock,
        minimum_stock=minimum_stock
    )
    db.add(db_item)
    db.flush()  # Generates the item ID safely

    # 2. Add an opening stock transaction record WITHOUT the invalid 'remarks' field
    if current_stock > 0:
        item_unit_price = price if price is not None else 0.0
        initial_transaction = models.Transaction(
            item_id=db_item.id,
            type="IN",                                # Matches your 'IN' operational token
            quantity=current_stock,
            user_id=1,                                # Default to your system admin/first user ID
            total_value=float(current_stock * item_unit_price) # Matches your pricing calculation
        )
        db.add(initial_transaction)

    db.commit()
    return RedirectResponse(url="/", status_code=303)


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

            name = clean_row.get("name") or clean_row.get("item name") or clean_row.get("item_name")
            item_code = clean_row.get("item_code") or clean_row.get("code") or clean_row.get("item code")

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


@app.post("/items/edit/{item_id}")
def edit_item(
    item_id: int,
    name: str = Form(...),
    item_code: str = Form(...),
    current_stock: int = Form(...),
    minimum_stock: int = Form(...),
    price: float = Form(...),
    session_user: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item:
        item.name = name.strip()
        item.item_code = item_code.strip().upper()
        item.current_stock = int(current_stock)
        item.minimum_stock = int(minimum_stock)
        item.price = float(price)
        
        db.commit()
        db.refresh(item)
        
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
        # Directly overwrite the inventory value to match exactly what you typed
        item.current_stock = int(new_stock)
        db.commit()
        db.refresh(item)
        
    return RedirectResponse(url="/", status_code=303)


@app.post("/material/issue")
def issue_materials(
    item_id: int = Form(...),
    quantity: int = Form(...),
    uom: str = Form(...),
    issued_to: str = Form(...),
    issued_by: str = Form(...),
    remarks: str = Form(None),
    db: Session = Depends(get_db)
):
    # Fetch the item
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item or item.current_stock < quantity:
        return RedirectResponse(url="/?error=insufficient_stock", status_code=303)

    # Deduct stock
    item.current_stock -= quantity

    # Create assignment record using your exact existing structure fields
    new_assignment = models.MaterialAssignment(
        item_id=item_id,
        quantity=quantity,
        uom=uom,
        issued_to=issued_to,
        issued_by=issued_by,
        remarks=remarks,
        custodian=issued_to # This maps directly into the Excel custodian structure automatically!
    )
    db.add(new_assignment)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/procurement/edit/{req_id}")
def edit_procurement_request(
    req_id: int,
    quantity: int = Form(...),
    department: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if not req:
        return HTMLResponse("<script>alert('Error: Request not found.'); window.location='/';</script>")
    
    # Only allow edits if the request is still Pending
    if req.status != "Pending":
        return HTMLResponse("<script>alert('Error: Cannot edit an already processed request.'); window.location='/';</script>")

    # Enforce rules: Requesters can edit their own; Admins can edit any pending request
    if current_user.role != "Admin" and req.requested_by_id != current_user.id:
        return HTMLResponse("<script>alert('Unauthorized: You can only edit your own requests.'); window.location='/';</script>")

    req.quantity = quantity
    req.department = department.strip()
    
    # Recalculate estimated cost based on the item rate
    rate = req.item.price if (req.item and req.item.price) else 0.0
    req.total_estimated_cost = float(quantity * rate)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/procurement/request")
def create_procurement_request(
    item_id: int = Form(...),
    quantity: int = Form(...),
    department: str = Form("Operations"),  # Captured Department
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    rate = item.price if (item and item.price) else 0.0
    db.add(models.ProcurementRequest(
        item_id=item_id,
        quantity=quantity,
        total_estimated_cost=float(quantity * rate),
        requested_by_id=current_user.id,
        department=department.strip(),
        status="Pending"
    ))
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
            req.status = "Accepted"
            if req.item:
                req.item.current_stock += req.quantity
                db.add(models.Transaction(
                    item_id=req.item_id,
                    type="IN_PO",
                    quantity=req.quantity,
                    user_id=current_user.id,
                    total_value=req.total_estimated_cost
                ))
        else:
            req.status = "Rejected"
        db.commit()
    return RedirectResponse(url="/", status_code=303)


# -------------------------------------------------------------
# MATERIAL REQUEST MODIFICATION & REMOVAL CONTROLLERS
# -------------------------------------------------------------

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
        
    # Fetch the request row
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/", status_code=303)
        
    # Fetch the chosen item to re-calculate estimated costs dynamically
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if item:
        req.item_id = item_id
        req.quantity = quantity
        req.total_estimated_cost = float(quantity * item.price)
        req.department = department
        db.commit()
        
    return RedirectResponse(url="/", status_code=303)


# -------------------------------------------------------------
# PROCUREMENT REQUEST DELETION ENDPOINT
# -------------------------------------------------------------
@app.get("/procurement/delete/{req_id}")
def delete_procurement_request(
    req_id: int,
    session_user: str = Cookie(None),
    db: Session = Depends(get_db)
):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)
        
    r = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == req_id).first()
    if r:
        db.delete(r)
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
        
    # Fetch and remove the request entry
    req = db.query(models.ProcurementRequest).filter(models.ProcurementRequest.id == request_id).first()
    if req:
        db.delete(req)
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


@app.get("/", response_class=HTMLResponse)
def root_dashboard(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    items = db.query(models.Item).all()
    reqs = db.query(models.ProcurementRequest).all()
    assignments = db.query(models.MaterialAssignment).all()
    employees = db.query(models.Employee).all()
    users = db.query(models.User).all()

    item_options = "".join([f'<option value="{i.id}">{i.name} ({i.item_code})</option>' for i in items])
    employee_options = "".join([f'<option value="{e.name}">{e.name} - {e.role_title}</option>' for e in employees])


    inventory_rows = """
    <script>
    if (!window.openEditItemModalDefined) {
        window.openEditItemModal = function(id, name, item_code, current_stock, minimum_stock, price) {
            let modal = document.getElementById('dynamicEditItemModal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'dynamicEditItemModal';
                modal.className = 'fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50';
                document.body.appendChild(modal);
            }
            modal.innerHTML = `
                <div class="bg-white rounded-xl border border-slate-200 shadow-2xl w-full max-w-md p-6 text-left relative animate-in fade-in zoom-in-95 duration-150" style="font-family: inherit; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);">
                    <h3 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2" style="font-size: 1.125rem; font-weight: 700; color: #0f172a; margin-bottom: 1rem;">📝 Edit Inventory Item</h3>
                    
                    <form action="/items/edit/${id}" method="POST" style="display: flex; flex-direction: column; gap: 1rem;">
                        <div>
                            <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Item Name</label>
                            <input type="text" name="name" value="${name.replace(/"/g, '&quot;')}" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; color: #1e293b;">
                        </div>
                        <div>
                            <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Item Code</label>
                            <input type="text" name="item_code" value="${item_code}" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; font-family: monospace; color: #475569; background-color: #f8fafc;">
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <div>
                                <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Price (₹)</label>
                                <input type="number" step="0.01" name="price" value="${price}" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; font-family: monospace; color: #1e293b;">
                            </div>
                            <div>
                                <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Safety Stock</label>
                                <input type="number" name="minimum_stock" value="${minimum_stock}" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; font-family: monospace; color: #1e293b;">
                            </div>
                        </div>
                        <div>
                            <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #64748b; text-transform: uppercase; margin-bottom: 0.25rem;">Current Stock Level</label>
                            <input type="number" name="current_stock" value="${current_stock}" required style="width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.375rem; font-size: 0.875rem; font-family: monospace; color: #1e293b;">
                        </div>
                        
                        <div style="display: flex; justify-content: flex-end; gap: 0.5rem; padding-top: 0.75rem; border-top: 1px solid #e2e8f0; margin-top: 0.5rem;">
                            <button type="button" onclick="document.getElementById('dynamicEditItemModal').remove()" style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 700; color: #475569; background-color: #f1f5f9; border: none; border-radius: 0.375rem; cursor: pointer;">Cancel</button>
                            <button type="submit" style="padding: 0.5rem 1rem; font-size: 0.75rem; font-weight: 700; color: white; background-color: #d97706; border: none; border-radius: 0.375rem; cursor: pointer;">Save Changes</button>
                        </div>
                    </form>
                </div>
            `;
        };
        window.openEditItemModalDefined = true;
    }
    </script>
    """
    for it in items:
        alert_status = ""
        if it.current_stock <= it.minimum_stock:
            alert_status = ' <span class="text-rose-600 font-black animate-pulse">⚠️ LOW</span>'
        
        # Pull spreadsheet metadata attributes safely
        item_cat = getattr(it, 'category', 'Consumables')
        item_sup = getattr(it, 'supplier', 'EIPL Approved Vendor')
        item_site = getattr(it, 'storage_site', 'Store Yard')

        # Strictly clean text fields to prevent quote collisions
        safe_name = it.name.replace("'", "\\'").replace('"', '\\"')
        safe_code = it.item_code.replace("'", "\\'").replace('"', '\\"')

        inventory_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/50">
            <td class="p-3 font-semibold text-slate-900">
                <span>{it.name}</span>{alert_status}
                <div class="text-[10px] text-slate-400 mt-0.5">
                    <span class="bg-slate-100 px-1 py-0.5 rounded text-slate-600">{item_cat}</span> 
                    • <span class="bg-blue-50 px-1 py-0.5 rounded text-blue-600">{item_site}</span>
                </div>
            </td>
            
            <td class="p-3 font-mono text-[11px] text-slate-500">{it.item_code}</td>
            <td class="p-3 text-slate-600 text-[11px] font-medium">{item_sup}</td>
            <td class="p-3 font-mono text-slate-600">₹{it.price:,.2f}</td>
            <td class="p-3 font-mono font-bold text-slate-900">{it.current_stock}</td>
            <td class="p-3 font-mono text-slate-400">{it.minimum_stock}</td>
            
            <td class="p-3">
                <div class="flex items-center gap-2">
                    <button type="button" onclick="openProcurementModal({it.id}, '{safe_name}')" class="text-indigo-600 hover:underline font-bold text-[11px]">Procure</button>
                    
                    <button type="button" onclick="openEditItemModal({it.id}, '{safe_name}', '{safe_code}', {it.current_stock}, {it.minimum_stock}, {it.price})" class="text-amber-600 hover:underline font-bold text-[11px]">
                        Edit
                    </button>
                    
                    <form action="/items/delete/{it.id}" method="POST" onsubmit="return confirm('Are you sure you want to completely remove this item from inventory records?');" class="inline m-0">
                        <button type="submit" class="text-rose-600 hover:underline font-bold text-[11px] bg-transparent border-none p-0 cursor-pointer inline">
                            Delete
                        </button>
                    </form>
                </div>
            </td>
        </tr>
        """


    req_rows = ""
    for r in reqs:
        date_str = r.timestamp.strftime("%d-%m %H:%M")
        badge = '<span class="bg-amber-100 text-amber-700 font-bold px-2 py-0.5 rounded text-[10px]">Pending</span>'
        if r.status == "Accepted":
            badge = '<span class="bg-emerald-100 text-emerald-700 font-bold px-2 py-0.5 rounded text-[10px]">Accepted</span>'
        elif r.status == "Rejected":
            badge = '<span class="bg-rose-100 text-rose-700 font-bold px-2 py-0.5 rounded text-[10px]">Rejected</span>'

        flow = ""
        if r.status == "Pending":
            edit_btn = ""
            if current_user.role == "Admin" or r.requested_by_id == current_user.id:
                escaped_dept = r.department.replace("'", "\\'")
                # Pass the item_id as the 4th parameter so the dropdown knows which option to highlight
                current_item_id = r.item_id if r.item_id else 0
                edit_btn = f"""<button onclick="openEditRequestModal({r.id}, {r.quantity}, '{escaped_dept}', {current_item_id})" class="text-indigo-600 font-bold hover:underline text-[10px] mr-2">Edit</button>"""

            if current_user.role == "Admin":
                flow = f"""
                <div class="flex items-center gap-1">
                    {edit_btn}
                    <form action="/procurement/action/{r.id}/accept" method="POST" class="inline">
                        <input type="submit" value="Approve" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-1.5 py-0.5 rounded cursor-pointer text-[10px] transition-colors">
                    </form>
                    <form action="/procurement/action/{r.id}/reject" method="POST" class="inline">
                        <input type="submit" value="Reject" class="bg-rose-600 hover:bg-rose-700 text-white font-bold px-1.5 py-0.5 rounded cursor-pointer text-[10px] transition-colors">
                    </form>
                </div>
                """
            else:
                flow = f"""<div class="flex items-center gap-1">{edit_btn} <span class="text-slate-400 italic text-[10px]">Awaiting Review</span></div>"""
        elif r.status == "Accepted":
            esc_name = r.item.name.replace("'", "\\'") if r.item else "Deleted Item"
            esc_code = r.item.item_code if r.item else "N/A"
            flow = f"""<button onclick="triggerInlinePOPrint({r.id}, '{esc_name}', '{esc_code}', {r.quantity})" class="bg-slate-700 hover:bg-slate-800 text-white text-[10px] font-bold px-2 py-0.5 rounded tracking-wide shadow-sm transition-all">🖨️ Print PO</button>"""
        else:
            flow = '<span class="text-slate-400 line-through text-[11px]">Closed</span>'

        item_desc_display = f"{r.item.name if r.item else 'Asset Disposed'}"
        if r.item:
            item_desc_display += f" <span class='text-[10px] text-slate-400 font-mono'>({r.item.item_code})</span>"
        if getattr(r, 'department', None):
            item_desc_display += f" <span class='text-[10px] text-indigo-600 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded'>[{r.department}]</span>"

        req_rows += f"""<tr class="border-b hover:bg-slate-50">
            <td class="p-3 text-slate-500 font-mono">{date_str}</td>
            <td class="p-3 font-bold text-slate-800">{item_desc_display}</td>
            <td class="p-3 font-mono font-semibold">{r.quantity}</td>
            <td class="p-3 font-mono text-slate-600">₹{r.total_estimated_cost:,.2f}</td>
            <td class="p-3 text-slate-500">{r.requester.username if r.requester else 'System'}</td>
            <td class="p-3">{badge}</td>
            <td class="p-3">{flow}</td>
        </tr>"""

    assigned_rows = ""
    for a in assignments:
        ts = a.timestamp.strftime("%d-%m %H:%M")
        assigned_rows += f"""<tr class="border-b hover:bg-slate-50">
            <td class="p-3 font-mono text-slate-400">{ts}</td>
            <td class="p-3 font-bold text-slate-800">{a.item.name if a.item else 'Archived Asset'}</td>
            <td class="p-3 font-mono text-blue-700 font-bold">{a.quantity} {a.uom}</td>
            <td class="p-3 text-slate-700 font-medium">{a.issued_to}</td>
            <td class="p-3 text-slate-500 font-mono">{a.issued_by}</td>
            <td class="p-3 text-slate-500 italic text-[11px]">{a.remarks or '-'}</td>
        </tr>"""

    employee_control_panel = ""
    admin_panel = ""
    user_directory_control_panel = ""

    # Generate the direct Sidebar Component for making procurement demands
    procurement_widget_panel = f"""
    <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-xl">
        <h2 class="text-xs font-black tracking-wider text-slate-500 uppercase border-b border-slate-200 pb-2 mb-4">❖ Material Procurement Requisition</h2>
        <form action="/procurement/request" method="POST" class="space-y-3 text-xs">
            <div>
                <label class="block font-semibold text-slate-500 mb-1">Select Item</label>
                <select name="item_id" class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">{item_options}</select>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Required Units</label>
                    <input type="number" name="quantity" min="1" value="5" required class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Department</label>
                    <input type="text" name="department" placeholder="e.g. Mechanical, Civil" required class="w-full bg-slate-50 border border-slate-300 text-slate-900 p-2.5 rounded-lg">
                </div>
            </div>
            <button type="submit" class="w-full bg-indigo-700 hover:bg-indigo-800 text-white p-2.5 rounded-lg font-bold transition-all shadow-sm">Submit Procurement Demand</button>
        </form>
    </div>
    """

    if current_user.role == "Admin":
        employee_list_markup = ""
        for e in employees:
            esc_emp_name = e.name.replace("'", "\\'")
            esc_emp_role = e.role_title.replace("'", "\\'")
            esc_emp_loc = e.location.replace("'", "\\'")
            esc_emp_contact = e.contact.replace("'", "\\'")
            employee_list_markup += f"""
            <div class='flex items-center justify-between bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px]'>
                <div class='space-y-0.5'>
                    <p class='font-bold text-slate-800'>{e.name}</p>
                    <p class='text-slate-500 text-[10px]'>{e.role_title} | Location: {e.location}</p>
                    <p class='text-slate-400 font-mono text-[9px]'>Ph: {e.contact}</p>
                </div>
                <div class='flex gap-1.5 ml-2'>
                    <button type='button' onclick="openEditEmployeeModal({e.id}, '{esc_emp_name}', '{esc_emp_role}', '{esc_emp_loc}', '{esc_emp_contact}')" class='text-indigo-600 font-bold hover:underline text-[10px]'>edit</button>
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
        <div class="bg-white p-6 rounded-xl border border-slate-200 shadow-xl mb-6">
            <div class="flex items-center justify-between border-b pb-2 mb-4">
                <h2 class="text-xs font-black tracking-wider text-slate-500 uppercase">❖ Update Item Manually</h2>
                <button type="button" onclick="downloadItemsCSVTemplate()" class="text-[10px] text-indigo-600 hover:underline font-bold">📥 Get Template</button>
            </div>
            <form action="/items/add" method="POST" class="space-y-3 text-xs">
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Item Name</label>
                        <input type="text" name="name" required placeholder="e.g. Steel Pipe" class="w-full bg-slate-50 border p-2.5 rounded-lg">
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Unique Item Code</label>
                        <input type="text" name="item_code" required placeholder="e.g. EIPL-ST-05" class="w-full bg-slate-50 border p-2.5 rounded-lg font-mono uppercase">
                    </div>
                </div>
                <div class="grid grid-cols-3 gap-2">
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Current Stock</label>
                        <input type="number" name="initial_stock" min="0" value="10" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Rate (₹)</label>
                        <input type="number" step="0.01" name="price" value="150.00" required class="w-full bg-slate-50 border p-2.5 rounded-lg">
                    </div>
                    <div>
                        <label class="block font-semibold text-slate-500 mb-1">Vendor/Supp.</label>
                        <input type="text" name="vendor" placeholder="Manufacturer" class="w-full bg-slate-50 border p-2.5 rounded-lg">
                    </div>
                </div>
                <div>
                    <label class="block font-semibold text-slate-500 mb-1">Project Site Location Placement</label>
                    <input type="text" name="site" placeholder="e.g. Udaipur Yard Base" class="w-full bg-slate-50 border p-2.5 rounded-lg">
                </div>
                <button type="submit" class="w-full bg-blue-950 text-white font-bold p-2.5 rounded-lg shadow-md">Add Core Catalog Line-Item</button>
            </form>
            <div class="pt-3 mt-3 border-t border-dashed border-slate-200">
                <label class="block font-black text-[10px] uppercase text-indigo-600 mb-1">📁 Bulk Catalog Import (CSV)</label>
                <form action="/items/bulk-import" method="POST" enctype="multipart/form-data" class="flex gap-2">
                    <input type="file" name="file" accept=".csv" required class="w-full bg-slate-50 border text-[10px] p-1 rounded-lg">
                    <button type="submit" class="bg-indigo-600 text-white px-2.5 py-1 rounded-lg font-bold text-[10px]">Import</button>
                </form>
            </div>
        </div>
        """

        user_list_markup = ""
        for u in users:
            esc_name = u.full_name.replace("'", "\\'")
            esc_desig = u.designation.replace("'", "\\'")
            esc_loc = u.workstation_location.replace("'", "\\'")
            user_list_markup += f"""
            <div class='flex items-center justify-between bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px]'>
                <div>
                    <p class='font-bold text-slate-800'>{u.username} ({u.role})</p>
                    <p class='text-slate-500 text-[10px]'>{u.full_name} - {u.designation}</p>
                </div>
                <div class='flex gap-1.5'>
                    <button type='button' onclick="openEditUserModal({u.id}, '{esc_name}', '{esc_desig}', '{esc_loc}', '{u.role}')" class='text-indigo-600 font-bold hover:underline text-[10px]'>edit</button>
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

    return templates.LAYOUT_HTML.replace("__USER__", current_user.username)\
                                .replace("__ROLE__", current_user.role)\
                                .replace("__USER_FULL_NAME__", current_user.full_name)\
                                .replace("__USER_DESIGNATION__", current_user.designation)\
                                .replace("__USER_LOCATION__", current_user.workstation_location)\
                                .replace("__ADMIN_PANEL__", admin_panel)\
                                .replace("__EMPLOYEE_CONTROL_PANEL__", employee_control_panel)\
                                .replace("__USER_DIRECTORY_CONTROL_PANEL__", user_directory_control_panel)\
                                .replace("__PROCUREMENT_WIDGET_PANEL__", procurement_widget_panel)\
                                .replace("__OPTIONS__", item_options)\
                                .replace("__EMPLOYEE_OPTIONS__", employee_options)\
                                .replace("__INVENTORY_ROWS__", inventory_rows)\
                                .replace("__REG_ROWS__", req_rows)\
                                .replace("__ASSIGNED_ROWS__", assigned_rows)

