# backend/crud.py
import random
import string
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from sqlalchemy.exc import IntegrityError
from datetime import date, datetime
from backend.auth import hash_password


# ==============================
# Helpers
# ==============================
def get_next_personal_code(db: Session) -> str:
    """Get next sequential personal code."""
    from backend import models
    max_code = db.query(func.max(models.User.personal_code.cast(Integer))).scalar()
    if max_code is None:
        return "1"
    else:
        return str(max_code + 1)


# ==============================
# Users (with Authentication)
# ==============================
def create_user(
    db: Session,
    email: str,
    password: str,
    name: str,
    whatsapp: str,
    branch: str,
    personal_code: str = None,
    role: str = "client"
):
    """Create a new user with hashed password."""
    from backend import models
    
    if not personal_code:
        personal_code = get_next_personal_code(db)
    
    hashed_password = hash_password(password)
    
    user = models.User(
        email=email,
        hashed_password=hashed_password,
        name=name,
        whatsapp=whatsapp,
        branch=branch,
        personal_code=personal_code,
        role=role,
        is_active=True
    )
    
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        print(f"[DB] Added user: {user.name}, code: {user.personal_code}, role: {user.role}")
    except IntegrityError as e:
        db.rollback()
        raise ValueError("Email, WhatsApp, or personal code already exists.")
    
    return user


def get_user_by_email(db: Session, email: str):
    """Get user by email."""
    from backend import models
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_personal_code(db: Session, personal_code: str):
    """Get user by personal code."""
    from backend import models
    return db.query(models.User).filter(models.User.personal_code == personal_code).first()


def update_last_login(db: Session, user_id: int):
    """Update user's last login timestamp."""
    from backend import models
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.last_login = datetime.utcnow()
        db.commit()


def list_users(db: Session):
    """List all users."""
    from backend import models
    return db.query(models.User).all()


def delete_user(db: Session, user_id: int):
    """Delete a user."""
    from backend import models
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        return True
    return False


# ==============================
# Tracks
# ==============================
def get_track_by_number(db: Session, track_number: str):
    """Get track by number."""
    from backend import models
    return db.query(models.Track).filter(models.Track.track_number == track_number).first()


def get_user_tracks_by_code(db: Session, personal_code: str, is_archived: bool = False):
    """Get all tracks for a user by personal code."""
    from backend import models
    return db.query(models.Track).filter(
        models.Track.personal_code == personal_code,
        models.Track.is_archived == is_archived
    ).all()


def create_or_update_track(db: Session, track_number: str, status: str, departure_date: date):
    """Create or update a track (admin function)."""
    from backend import models
    track = get_track_by_number(db, track_number)
    
    if track:
        track.status = status
        track.departure_date = departure_date
        track.is_archived = False  # Unarchive if was archived
        track.updated_at = datetime.utcnow()
        db.commit()
        print(f"[DB] Updated track: {track_number} to status '{status}'")
    else:
        track = models.Track(
            track_number=track_number,
            status=status,
            departure_date=departure_date,
            personal_code=None,
            is_archived=False
        )
        db.add(track)
        db.commit()
        print(f"[DB] Created new unassigned track: {track_number} with status '{status}'")
    
    return track


def assign_track_to_user(db: Session, track_number: str, personal_code: str):
    """Assign a track to a user."""
    from backend import models
    track = get_track_by_number(db, track_number)
    
    if track:
        if track.personal_code and track.personal_code != personal_code:
            raise ValueError(f"Track {track_number} is already assigned to another client.")
        track.personal_code = personal_code
        track.updated_at = datetime.utcnow()
        db.commit()
        print(f"[DB] Assigned track {track_number} to user {personal_code}")
        return track
    else:
        new_track = models.Track(
            track_number=track_number,
            status="Дата регистрации клиентом",
            departure_date=None,
            personal_code=personal_code,
            is_archived=False
        )
        db.add(new_track)
        db.commit()
        db.refresh(new_track)
        print(f"[DB] Registered new track {track_number} by user {personal_code}")
        return new_track


def archive_track(db: Session, track_number: str):
    """Archive a track (soft delete)."""
    from backend import models
    track = get_track_by_number(db, track_number)
    if track:
        track.is_archived = True
        track.updated_at = datetime.utcnow()
        db.commit()
        return True
    return False


# ==============================
# Audit Logs
# ==============================
def create_audit_log(
    db: Session,
    action: str,
    performed_by: str,
    target_entity: str,
    target_id: str,
    details: str = None
):
    """Create an audit log entry."""
    from backend import models
    log = models.AuditLog(
        action=action,
        performed_by=performed_by,
        target_entity=target_entity,
        target_id=target_id,
        details=details
    )
    db.add(log)
    db.commit()
    print(f"[AUDIT] {action} by {performed_by} on {target_entity}:{target_id}")
