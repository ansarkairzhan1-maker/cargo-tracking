from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime
from datetime import datetime
from .db import Base

# =======================================================
# USER MODEL (with Authentication)
# =======================================================
class User(Base):
    """
    SQLAlchemy model for 'users' table with authentication fields.
    """
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    branch = Column(String(255))
    whatsapp = Column(String(255), unique=True, index=True)
    personal_code = Column(String(255), unique=True, index=True)
    
    # Authentication fields
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="client")  # "admin" or "client"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


# =======================================================
# TRACK MODEL
# =======================================================
class Track(Base):
    """
    SQLAlchemy model for 'tracks' table.
    """
    __tablename__ = "tracks"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True, index=True)
    track_number = Column(String(255), unique=True, index=True)
    status = Column(String(255))
    name = Column(String(255), nullable=True)
    branch = Column(String(255), nullable=True)
    whatsapp = Column(String(255), index=True, nullable=True)
    personal_code = Column(String(255), index=True, nullable=True)
    departure_date = Column(Date, nullable=True)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =======================================================
# AUDIT LOG MODEL (for tracking admin actions)
# =======================================================
class AuditLog(Base):
    """
    SQLAlchemy model for audit logging.
    """
    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100))  # "create_user", "update_track", etc.
    performed_by = Column(String(255))  # user email
    target_entity = Column(String(100))  # "user", "track"
    target_id = Column(String(255))
    details = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
