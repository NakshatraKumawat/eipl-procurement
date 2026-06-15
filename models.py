import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Boolean, LargeBinary

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="Staff")
    full_name = Column(String, default="EIPL Officer")
    designation = Column(String, default="Operations Specialist")
    workstation_location = Column(String, default="Corporate HQ")


class ItemLot(Base):
    """
    Represents one (item, vendor, price) batch of stock.
    The same item_code can have multiple lots from different vendors
    or the same vendor at different prices over time. The sum of
    `quantity` across all lots for an item equals `Item.current_stock`.
    Outward transactions consume lots oldest-first (FIFO by received_at).
    """
    __tablename__ = "item_lots"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), index=True)
    vendor = Column(String, default="Approved Vendor")
    price = Column(Float, default=0.0)
    quantity = Column(Integer, default=0)
    received_at = Column(DateTime, default=datetime.datetime.utcnow)

    item = relationship("Item")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String, unique=True, index=True) # ProductID
    name = Column(String, index=True)                  # Product Description
    # Category controls serial tracking:
    #   "Fixed Assets and Equipments" -> serial-tracked via AssetUnit
    #   "Consumables" / "Tools and Tackles" -> count-based (lots)
    category = Column(String, default="Consumables")
    description = Column(String)
    supplier = Column(String, default="Approved Vendor")
    storage_site = Column(String, default="Store Yard")
    price = Column(Float, default=0.0)
    current_stock = Column(Integer, default=0)
    minimum_stock = Column(Integer, default=0)
    uom = Column(String, nullable=True)  # Fixed once set — cannot be changed after first transaction


class AssetUnit(Base):
    """One physical unit of a serial-tracked item (Fixed Assets and Equipments).
    Identity persists across its whole lifecycle:
        In Stock -> Issued -> (returned) -> In Stock -> ... -> Retired
    `current_holder` is populated only while `status == 'Issued'`."""
    __tablename__ = "asset_units"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), index=True)
    serial_no = Column(String, unique=True, index=True)
    status = Column(String, default="In Stock")        # "In Stock" | "Issued" | "Retired"
    current_holder = Column(String, nullable=True)
    current_assignment_id = Column(Integer, ForeignKey("material_assignments.id"), nullable=True)
    acquired_at = Column(DateTime, default=datetime.datetime.utcnow)
    retired_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

    item = relationship("Item")


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    role_title = Column(String)
    location = Column(String, default="Not Specified")
    contact = Column(String, default="Not Specified")


class ProcurementRequest(Base):
    __tablename__ = "procurement_requests"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True) # Changed to nullable for new items
    quantity = Column(Integer)
    total_estimated_cost = Column(Float)
    requested_by_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="Pending")
    department = Column(String, default="General Operations")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # --- ADDED NEW TRACKING COLUMNS FOR AD-HOC ITEMS ---
    is_new_item = Column(Boolean, default=False)
    new_item_name = Column(String, nullable=True)
    detailed_specification = Column(String, nullable=True)

    # --- ADMIN-ENTERED PROCUREMENT PRICING (gates the Order button) ---
    vendor = Column(String, nullable=True)        # Vendor chosen by admin before ordering
    unit_price = Column(Float, nullable=True)      # Per-unit rate entered by admin before ordering

    # --- ASSET CLASS CATEGORY (Fixed Assets and Equipments / Consumables / Tools and Tackles) ---
    category = Column(String, nullable=True)

    item = relationship("Item")
    requester = relationship("User")

class MaterialAssignment(Base):
    __tablename__ = "material_assignments"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    quantity = Column(Integer)
    uom = Column(String)
    issued_to = Column(String)
    issued_by = Column(String)
    department = Column(String, default="General Operations")       # Department of receiver
    remarks = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    # --- ADDED FROM EXCEL ASSET ALLOCATION ---
    custodian = Column(String, default="Common")                    # Tracks permanent allocation to individual users
    # --- MIS UPLOAD TRACKING ---
    mis_filename = Column(String, nullable=True)                    # Material Issue Slip file
    mis_filedata = Column(LargeBinary, nullable=True)               # File bytes stored in shared DB (cross-device)
    mis_uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    mis_upload_timestamp = Column(DateTime, nullable=True)
    # --- RETURN-TO-STORE TRACKING (same table; is_return flips direction) ---
    is_return = Column(Boolean, default=False)                      # True for return-to-store rows
    return_filename = Column(String, nullable=True)                 # Return-to-Store slip filename
    return_filedata = Column(LargeBinary, nullable=True)            # Return-to-Store slip bytes (shared DB)
    # --- SERIAL-TRACKED ASSET LINK (NULL for consumables and tools) ---
    asset_unit_id = Column(Integer, ForeignKey("asset_units.id"), nullable=True)

    item = relationship("Item")
    mis_uploader = relationship("User", foreign_keys=[mis_uploaded_by_id])


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    type = Column(String)
    quantity = Column(Integer)
    total_value = Column(Float, default=0.0)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


# =========================================================================
# UPDATED PORTION OF MODELS.PY (MaterialRequest Table Structural Extension)
# =========================================================================
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Boolean

class MaterialRequest(Base):
    __tablename__ = "material_requests"
    id = Column(Integer, primary_key=True, index=True)
    
    # Linked item is now nullable to allow ad-hoc new custom orders
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    quantity = Column(Integer)
    total_estimated_cost = Column(Float, default=0.0)
    requested_by_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="Pending")
    department = Column(String, default="General Operations")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # NEW COLUMNS FOR AD-HOC EXTRACTION DATA
    is_new_item = Column(Boolean, default=False)
    new_item_name = Column(String, nullable=True)
    detailed_specification = Column(String, nullable=True)

    item = relationship("Item")
    requester = relationship("User")

class ProcurementMessage(Base):
    __tablename__ = "procurement_messages"
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("procurement_requests.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    request = relationship("ProcurementRequest")
    sender = relationship("User")


class GRNRecord(Base):
    __tablename__ = "grn_records"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    quantity = Column(Integer)
    uom = Column(String, default="Nos")
    received_by = Column(String, nullable=True)
    vendor = Column(String, nullable=True)            # Vendor for THIS inward batch (per-transaction, not catalog)
    unit_price = Column(Float, nullable=True)          # Per-unit price for THIS inward batch
    grn_no = Column(String, nullable=True)             # GRN reference number entered at inward
    challan_no = Column(String, nullable=True)         # Challan / Invoice number entered at inward
    grn_filename = Column(String)
    grn_filedata = Column(LargeBinary, nullable=True)  # File bytes stored in shared DB (cross-device)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    item = relationship("Item")
    uploader = relationship("User")
