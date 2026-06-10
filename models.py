import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base


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
    item_id = Column(Integer, ForeignKey("items.id"))
    quantity = Column(Integer)
    total_estimated_cost = Column(Float)
    requested_by_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="Pending")
    department = Column(String, default="General Operations")  # Added Department column
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

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
    remarks = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    # --- ADDED FROM EXCEL ASSET ALLOCATION ---
    custodian = Column(String, default="Common")                    # Tracks permanent allocation to individual users

    item = relationship("Item")


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    type = Column(String)
    quantity = Column(Integer)
    total_value = Column(Float, default=0.0)
    user_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)