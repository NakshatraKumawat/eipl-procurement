import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Boolean

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="Staff")
    full_name = Column(String, default="EIPL Officer")
    designation = Column(String, default="Operations Specialist")
    workstation_location = Column(String, default="Corporate HQ")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String, unique=True, index=True) # ProductID
    name = Column(String, index=True)                  # Product Description
    category = Column(String, default="Consumables")
    description = Column(String)
    supplier = Column(String, default="Approved Vendor")
    storage_site = Column(String, default="Store Yard")
    price = Column(Float, default=0.0)
    current_stock = Column(Integer, default=0)
    minimum_stock = Column(Integer, default=0)


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
    mis_uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    mis_upload_timestamp = Column(DateTime, nullable=True)

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
    grn_filename = Column(String)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    item = relationship("Item")
    uploader = relationship("User")
