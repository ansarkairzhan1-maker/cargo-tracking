# backend/main.py
import os
import datetime
from datetime import timedelta
from typing import List
from fastapi import FastAPI, HTTPException, Form, Depends, UploadFile, File, status, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import shutil
import pandas as pd
from io import BytesIO

# Rate limiting imports
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import db
from .models import User, Track
import backend.crud as crud
import backend.auth as auth
from backend.schemas import UserRegister, UserLogin, Token, UserOut, TrackAssignment

# Initialize FastAPI app
app = FastAPI(title="Delta Cargo Admin")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
FRONTEND_SRC_DIR = os.path.join(FRONTEND_DIR, "src")

# Mount static files
app.mount("/static", StaticFiles(directory=FRONTEND_SRC_DIR), name="static")


# =======================================================
# STARTUP AND SHUTDOWN EVENTS
# =======================================================

@app.on_event("startup")
def startup_event():
    """Initialize database on application startup."""
    db.initialize_database()
    db.Base.metadata.create_all(bind=db.engine)
    print("[DB] Database tables created/checked.")
    print(f"[APP] Application started successfully")


@app.on_event("shutdown")
def shutdown_event():
    """Cleanup on application shutdown."""
    db.close_database()
    print("[APP] Application shutdown complete")


# =======================================================
# HTML SERVING
# =======================================================

@app.get("/")
def redirect_to_index():
    """Serve main index page."""
    path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File index.html not found")
    return FileResponse(path)


@app.get("/admin")
def admin_page():
    """Serve admin panel page."""
    path = os.path.join(FRONTEND_DIR, "admin.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File admin.html not found")
    return FileResponse(path)


@app.get("/login")
def login_page():
    """Serve login page."""
    path = os.path.join(FRONTEND_DIR, "login.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File login.html not found")
    return FileResponse(path)


# =======================================================
# HEALTH CHECK
# =======================================================

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    db_healthy = db.check_database_health()
    db_info = db.get_database_info()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": {
            "type": db_info["type"],
            "healthy": db_healthy
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    }


# =======================================================
# AUTHENTICATION ENDPOINTS WITH RATE LIMITING
# =======================================================

@app.post("/api/auth/register", response_model=UserOut)
@limiter.limit("3/hour")  # Max 3 registrations per hour per IP
def register_user(
    request: Request,
    user_data: UserRegister,
    session: Session = Depends(db.get_db)
):
    """Register a new client user."""
    try:
        user = crud.create_user(
            db=session,
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
            whatsapp=user_data.whatsapp,
            branch=user_data.branch,
            personal_code=user_data.personal_code,
            role="client"
        )
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login", response_model=Token)
@limiter.limit("5/minute")  # Max 5 login attempts per minute per IP
def login_user(
    request: Request,
    login_data: UserLogin,
    session: Session = Depends(db.get_db)
):
    """
    Login user and return JWT token.
    Rate limited to prevent brute force attacks.
    """
    # Authenticate user with email and password
    user = auth.authenticate_user(session, login_data.email, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Update last login timestamp
    crud.update_last_login(session, user.id)
    
    # Create JWT access token
    access_token = auth.create_user_token(user)
    
    # Return token with user information
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "personal_code": user.personal_code,
            "role": user.role,
            "branch": user.branch,
            "whatsapp": user.whatsapp
        }
    }


@app.get("/api/auth/me", response_model=UserOut)
def get_current_user_info(
    current_user: User = Depends(auth.get_current_active_user)
):
    """Get current authenticated user information."""
    return current_user


# =======================================================
# PASSWORD MANAGEMENT
# =======================================================

@app.post("/api/auth/change-password")
@limiter.limit("3/hour")  # Max 3 password changes per hour
def change_own_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.get_current_active_user)
):
    """User endpoint to change their own password."""
    if not auth.verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password"
        )
    
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters"
        )
    
    if old_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    current_user.hashed_password = auth.hash_password(new_password)
    session.commit()
    
    crud.create_audit_log(
        session,
        action="change_password",
        performed_by=current_user.email,
        target_entity="user",
        target_id=str(current_user.id),
        details="User changed their own password"
    )
    
    return {
        "success": True,
        "message": "Password changed successfully"
    }


@app.post("/api/admin/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    new_password: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to reset user password."""
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = auth.hash_password(new_password)
    session.commit()
    
    crud.create_audit_log(
        session,
        action="reset_password",
        performed_by=current_user.email,
        target_entity="user",
        target_id=str(user_id),
        details=f"Password reset for user {user.email}"
    )
    
    return {
        "success": True,
        "user_email": user.email,
        "new_password": new_password,
        "message": "Password reset successful"
    }


@app.post("/api/admin/users/{user_id}/generate-password")
def generate_random_password_for_user(
    user_id: int,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to generate and set random password."""
    import secrets
    import string
    
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for i in range(8))
    
    user.hashed_password = auth.hash_password(new_password)
    session.commit()
    
    crud.create_audit_log(
        session,
        action="generate_password",
        performed_by=current_user.email,
        target_entity="user",
        target_id=str(user_id),
        details=f"Generated new password for user {user.email}"
    )
    
    return {
        "success": True,
        "user_email": user.email,
        "user_name": user.name,
        "new_password": new_password,
        "message": "Random password generated"
    }


# =======================================================
# USER MANAGEMENT (ADMIN ONLY)
# =======================================================

@app.post("/api/users")
def add_user_admin(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    whatsapp: str = Form(...),
    branch: str = Form(...),
    personal_code: str = Form(None),
    role: str = Form("client"),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to create new users."""
    try:
        user = crud.create_user(
            session, email, password, name, whatsapp, branch, personal_code, role
        )
        
        crud.create_audit_log(
            session,
            action="create_user",
            performed_by=current_user.email,
            target_entity="user",
            target_id=str(user.id),
            details=f"Created user {user.email} with role {role}"
        )
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "whatsapp": user.whatsapp,
            "branch": user.branch,
            "personal_code": user.personal_code,
            "role": user.role
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/users")
def get_all_users(
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to list all users."""
    users = crud.list_users(session)
    return [{
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "whatsapp": u.whatsapp,
        "branch": u.branch,
        "personal_code": u.personal_code,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None
    } for u in users]


@app.delete("/api/users/{user_id}")
def delete_user_by_id(
    user_id: int,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to delete a user."""
    success = crud.delete_user(session, user_id)
    if success:
        crud.create_audit_log(
            session,
            action="delete_user",
            performed_by=current_user.email,
            target_entity="user",
            target_id=str(user_id)
        )
        return {"message": "User deleted successfully"}
    raise HTTPException(status_code=404, detail="User not found")


# Continue with rest of your endpoints (tracks, scanner, calendar, etc.)
# ... (add all other endpoints from previous code)

# =======================================================
# USER MANAGEMENT (ADMIN ONLY)
# =======================================================
@app.post("/api/users")
def add_user_admin(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    whatsapp: str = Form(...),
    branch: str = Form(...),
    personal_code: str = Form(None),
    role: str = Form("client"),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to create new users."""
    try:
        user = crud.create_user(
            session, email, password, name, whatsapp, branch, personal_code, role
        )
        
        # Log action
        crud.create_audit_log(
            session,
            action="create_user",
            performed_by=current_user.email,
            target_entity="user",
            target_id=str(user.id),
            details=f"Created user {user.email} with role {role}"
        )
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "whatsapp": user.whatsapp,
            "branch": user.branch,
            "personal_code": user.personal_code,
            "role": user.role
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/users")
def get_all_users(
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to list all users."""
    users = crud.list_users(session)
    return [{
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "whatsapp": u.whatsapp,
        "branch": u.branch,
        "personal_code": u.personal_code,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None
    } for u in users]


@app.delete("/api/users/{user_id}")
def delete_user_by_id(
    user_id: int,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to delete a user."""
    success = crud.delete_user(session, user_id)
    if success:
        crud.create_audit_log(
            session,
            action="delete_user",
            performed_by=current_user.email,
            target_entity="user",
            target_id=str(user_id)
        )
        return {"message": "User deleted successfully"}
    raise HTTPException(status_code=404, detail="User not found")


# =======================================================
# TRACK TIMELINE GENERATION (FIXED DATES)
# =======================================================
def generate_track_timeline(track):
    """Generate timeline events for a track with CORRECTED dates."""
    STATUS_FLOW = [
        ("Дата регистрации клиентом", 0),
        ("Выехал из склада Китая", 0),        # Shows actual departure date
        ("В транзитном складе", 5),            # 5 days after China departure
        ("В Алматы (Склад)", 10),              # 10 days after China departure  
        ("В Астане (Склад)", 10),              # Same as Almaty (parallel)
        ("Выдан клиенту", 15),                 # 15 days after China departure
    ]
    
    current_status = track.status if track.status else STATUS_FLOW[0][0]
    try:
        current_status_index = next(
            i for i, flow in enumerate(STATUS_FLOW) if flow[0] == current_status
        )
    except StopIteration:
        current_status_index = 0
    
    events = []
    departure_date_base = track.departure_date or datetime.datetime.now().date()
    
    for i, (status, day_offset) in enumerate(STATUS_FLOW):
        is_completed = i <= current_status_index
        event_date_str = "нет данных"
        
        if is_completed:
            if i == 0:
                # Client registration date
                if hasattr(track, 'created_at') and track.created_at:
                    event_date = track.created_at
                else:
                    event_date = datetime.datetime.combine(datetime.datetime.now().date(), datetime.datetime.min.time())
            elif i == 1:
                # Departure from China - use EXACT departure_date
                if track.departure_date:
                    event_date = datetime.datetime.combine(track.departure_date, datetime.datetime.min.time())
                else:
                    event_date = datetime.datetime.combine(datetime.datetime.now().date(), datetime.datetime.min.time())
            else:
                # Other statuses - calculate from departure date
                event_date = datetime.datetime.combine(
                    departure_date_base, datetime.datetime.min.time()
                ) + timedelta(days=day_offset)
            
            event_date_str = event_date.strftime("%d.%m.%Y %H:%M")
        
        events.append(
            {"status": status, "date": event_date_str, "completed": is_completed}
        )
    
    return events


# =======================================================
# TRACK QUERY ENDPOINTS (AUTHENTICATED)
# =======================================================
@app.get("/api/tracks/search/{track_number}")
def search_track(
    track_number: str,
    session: Session = Depends(db.get_db)
):
    """Public track search (no authentication required)."""
    track = crud.get_track_by_number(session, track_number)
    if not track:
        raise HTTPException(
            status_code=404,
            detail="Track not found. It may appear soon.",
        )
    return {
        "track_number": track.track_number,
        "current_status": track.status,
        "is_assigned": track.personal_code is not None,
        "personal_code": track.personal_code,
        "departure_date": (
            track.departure_date.isoformat() if track.departure_date else None
        ),
        "status_timeline": generate_track_timeline(track),
    }


@app.get("/api/users/{personal_code}/tracks")
def get_user_active_tracks(
    personal_code: str,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.get_current_active_user)
):
    """Get user's active (non-archived) tracks."""
    if current_user.role != "admin" and current_user.personal_code != personal_code:
        raise HTTPException(status_code=403, detail="Access denied")
    
    tracks = crud.get_user_tracks_by_code(session, personal_code, is_archived=False)
    return [{
        "track_number": t.track_number,
        "status": t.status,
        "departure_date": t.departure_date.isoformat() if t.departure_date else None,
        "personal_code": t.personal_code,
        "status_timeline": generate_track_timeline(t)
    } for t in tracks]


@app.get("/api/users/{personal_code}/tracks/archived")
def get_user_archived_tracks(
    personal_code: str,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.get_current_active_user)
):
    """Get user's archived tracks."""
    if current_user.role != "admin" and current_user.personal_code != personal_code:
        raise HTTPException(status_code=403, detail="Access denied")
    
    tracks = crud.get_user_tracks_by_code(session, personal_code, is_archived=True)
    return [{
        "track_number": t.track_number,
        "status": t.status,
        "departure_date": t.departure_date.isoformat() if t.departure_date else None,
        "personal_code": t.personal_code,
        "status_timeline": generate_track_timeline(t)
    } for t in tracks]


# =======================================================
# TRACK MODIFICATION ENDPOINTS
# =======================================================
@app.post("/api/tracks/assign")
def assign_track_endpoint(
    request: TrackAssignment,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.get_current_active_user)
):
    """Client endpoint to assign a track to themselves."""
    if current_user.role != "admin" and current_user.personal_code != request.personal_code:
        raise HTTPException(status_code=403, detail="You can only assign tracks to yourself")
    
    try:
        assigned_track = crud.assign_track_to_user(
            session, request.track_number, request.personal_code
        )
        timeline = generate_track_timeline(assigned_track)
        return {
            "track_number": assigned_track.track_number,
            "status": assigned_track.status,
            "departure_date": (
                assigned_track.departure_date.isoformat()
                if assigned_track.departure_date
                else None
            ),
            "personal_code": assigned_track.personal_code,
            "status_timeline": timeline,
            "message": "Track successfully added. Await status update.",
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/tracks/archive/{track_number}")
def archive_track_endpoint(
    track_number: str,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.get_current_active_user)
):
    """Archive a track (soft delete)."""
    track = crud.get_track_by_number(session, track_number)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    if current_user.role != "admin" and track.personal_code != current_user.personal_code:
        raise HTTPException(status_code=403, detail="Access denied")
    
    success = crud.archive_track(session, track_number)
    if success:
        return {"message": "Track archived successfully"}
    raise HTTPException(status_code=500, detail="Failed to archive track")


@app.post("/api/tracks")
async def upload_tracks(
    file: UploadFile = File(...),
    departure_date: str = Form(...),
    status: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint for bulk track upload."""
    count = 0
    processed_tracks = []
    errors = []
    
    try:
        departure_dt = datetime.datetime.strptime(departure_date, "%Y-%m-%d").date()
        contents = await file.read()
        
        if file.filename.endswith(".xlsx"):
            df = pd.read_excel(BytesIO(contents), header=None)
        elif file.filename.endswith(".csv"):
            df = pd.read_csv(BytesIO(contents), header=None)
        else:
            track_numbers = contents.decode("utf-8").splitlines()
            df = pd.DataFrame(track_numbers)
        
        track_numbers = df[0].dropna().astype(str).str.strip()
        
        for track_number in track_numbers:
            if track_number and track_number != "nan":
                try:
                    crud.create_or_update_track(
                        session,
                        track_number,
                        status,
                        departure_dt,
                    )
                    processed_tracks.append(track_number)
                    count += 1
                except Exception as track_error:
                    error_msg = f"Error processing track {track_number}: {str(track_error)}"
                    errors.append(error_msg)
        
        session.commit()
        
        crud.create_audit_log(
            session,
            action="bulk_upload_tracks",
            performed_by=current_user.email,
            target_entity="track",
            target_id="bulk",
            details=f"Uploaded {count} tracks with status '{status}'"
        )
        
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Use YYYY-MM-DD. Error: {str(ve)}",
        )
    
    return {
        "success": True,
        "count": count,
        "processed_tracks": processed_tracks[:10],
        "errors": errors[:5] if errors else [],
        "total_errors": len(errors),
    }

# =======================================================
# PASSWORD MANAGEMENT ENDPOINTS (NEW)
# =======================================================

@app.post("/api/auth/change-password")
def change_own_password(
    old_password: str = Form(...),
    new_password: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.get_current_active_user)
):
    """User endpoint to change their own password."""
    if not auth.verify_password(old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect current password"
        )
    
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters"
        )
    
    if old_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    current_user.hashed_password = auth.hash_password(new_password)
    session.commit()
    
    crud.create_audit_log(
        session,
        action="change_password",
        performed_by=current_user.email,
        target_entity="user",
        target_id=str(current_user.id),
        details="User changed their own password"
    )
    
    return {
        "success": True,
        "message": "Password changed successfully"
    }


@app.post("/api/admin/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    new_password: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to reset user password."""
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = auth.hash_password(new_password)
    session.commit()
    
    crud.create_audit_log(
        session,
        action="reset_password",
        performed_by=current_user.email,
        target_entity="user",
        target_id=str(user_id),
        details=f"Password reset for user {user.email}"
    )
    
    return {
        "success": True,
        "user_email": user.email,
        "new_password": new_password,
        "message": "Password reset successful"
    }


@app.post("/api/admin/users/{user_id}/generate-password")
def generate_random_password_for_user(
    user_id: int,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to generate and set random password."""
    import secrets
    import string
    
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for i in range(8))
    
    user.hashed_password = auth.hash_password(new_password)
    session.commit()
    
    crud.create_audit_log(
        session,
        action="generate_password",
        performed_by=current_user.email,
        target_entity="user",
        target_id=str(user_id),
        details=f"Generated new password for user {user.email}"
    )
    
    return {
        "success": True,
        "user_email": user.email,
        "user_name": user.name,
        "new_password": new_password,
        "message": "Random password generated"
    }


# =======================================================
# TRACK MANAGEMENT ENDPOINTS (NEW)
# =======================================================

@app.put("/api/admin/tracks/{track_number}/status")
def update_track_status(
    track_number: str,
    new_status: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to update a single track status."""
    track = crud.get_track_by_number(session, track_number)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    old_status = track.status
    track.status = new_status
    track.updated_at = datetime.datetime.utcnow()
    session.commit()
    
    return {
        "success": True,
        "track_number": track_number,
        "old_status": old_status,
        "new_status": new_status
    }


@app.delete("/api/admin/tracks/{track_number}")
def delete_track_permanently(
    track_number: str,
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Admin endpoint to permanently delete a track."""
    track = crud.get_track_by_number(session, track_number)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    session.delete(track)
    session.commit()
    
    return {"success": True, "message": f"Track {track_number} deleted"}


# =======================================================
# BARCODE SCANNER ENDPOINTS (NEW)
# =======================================================

@app.post("/api/admin/scanner/validate")
def validate_scanned_tracks(
    track_numbers: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Validate scanned track numbers."""
    track_list = [t.strip().upper() for t in track_numbers.split(',') if t.strip()]
    
    results = []
    for track_num in track_list:
        track = crud.get_track_by_number(session, track_num)
        if track:
            results.append({
                "track_number": track.track_number,
                "status": track.status,
                "personal_code": track.personal_code,
                "found": True,
                "can_deliver": track.status in ["В Алматы (Склад)", "В Астане (Склад)"]
            })
        else:
            results.append({
                "track_number": track_num,
                "found": False,
                "error": "Track not found in system"
            })
    
    return {
        "total_scanned": len(track_list),
        "found": len([r for r in results if r.get("found")]),
        "not_found": len([r for r in results if not r.get("found")]),
        "results": results
    }


@app.post("/api/admin/scanner/deliver")
def deliver_scanned_parcels(
    track_numbers: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Mark scanned parcels as delivered."""
    track_list = [t.strip().upper() for t in track_numbers.split(',') if t.strip()]
    
    delivered_count = 0
    errors = []
    
    for track_num in track_list:
        track = crud.get_track_by_number(session, track_num)
        if track:
            track.status = "Выдан клиенту"
            track.updated_at = datetime.datetime.utcnow()
            delivered_count += 1
        else:
            errors.append(f"{track_num}: not found")
    
    session.commit()
    
    return {
        "success": True,
        "delivered_count": delivered_count,
        "errors": errors
    }


@app.post("/api/admin/scanner/delete")
def delete_scanned_parcels(
    track_numbers: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Permanently delete scanned parcels."""
    track_list = [t.strip().upper() for t in track_numbers.split(',') if t.strip()]
    
    deleted_count = 0
    errors = []
    
    for track_num in track_list:
        track = crud.get_track_by_number(session, track_num)
        if track:
            session.delete(track)
            deleted_count += 1
        else:
            errors.append(f"{track_num}: not found")
    
    session.commit()
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "errors": errors
    }


# =======================================================
# CALENDAR ENDPOINTS (NEW)
# =======================================================

@app.get("/api/admin/tracks-by-date")
def get_tracks_by_departure_date(
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Get all tracks grouped by departure date for calendar."""
    tracks = session.query(Track).filter(
        Track.departure_date.isnot(None)
    ).all()
    
    dates_dict = {}
    for track in tracks:
        date_str = track.departure_date.isoformat()
        if date_str not in dates_dict:
            dates_dict[date_str] = []
        dates_dict[date_str].append({
            'track_number': track.track_number,
            'status': track.status,
            'personal_code': track.personal_code,
            'is_assigned': track.personal_code is not None
        })
    
    calendar_events = []
    for date_str, tracks_list in dates_dict.items():
        calendar_events.append({
            'date': date_str,
            'title': f"{len(tracks_list)} посылок",
            'count': len(tracks_list),
            'tracks': tracks_list
        })
    
    return calendar_events


@app.post("/api/admin/batch-update-status")
def batch_update_status_by_date(
    departure_date: str = Form(...),
    new_status: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Update status for all tracks from specific departure date."""
    try:
        dep_date = datetime.datetime.strptime(departure_date, "%Y-%m-%d").date()
        
        tracks = session.query(Track).filter(
            Track.departure_date == dep_date
        ).all()
        
        if not tracks:
            raise HTTPException(status_code=404, detail="No tracks found for this date")
        
        updated_count = 0
        for track in tracks:
            track.status = new_status
            track.updated_at = datetime.datetime.utcnow()
            updated_count += 1
        
        session.commit()
        
        return {
            "success": True,
            "updated_count": updated_count,
            "departure_date": departure_date,
            "new_status": new_status,
            "tracks": [t.track_number for t in tracks[:10]]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

# TRACK MANAGEMENT ENDPOINTS (NEW)
@app.put("/api/admin/tracks/{track_number}/status")
def update_track_status(
    track_number: str,
    new_status: str = Form(...),
    session: Session = Depends(db.get_db),
):
    """Admin endpoint to update a single track status."""
    track = crud.get_track_by_number(session, track_number)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    old_status = track.status
    track.status = new_status
    track.updated_at = datetime.datetime.utcnow()
    session.commit()
    
    return {
        "success": True,
        "track_number": track_number,
        "old_status": old_status,
        "new_status": new_status
    }


@app.delete("/api/admin/tracks/{track_number}")
def delete_track_permanently(
    track_number: str,
    session: Session = Depends(db.get_db),
):
    """Admin endpoint to permanently delete a track."""
    track = crud.get_track_by_number(session, track_number)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    session.delete(track)
    session.commit()
    
    return {"success": True, "message": f"Track {track_number} deleted"}


# BARCODE SCANNER - BATCH DELIVERY ENDPOINTS (NEW)
@app.post("/api/admin/scanner/validate")
def validate_scanned_tracks(
    track_numbers: str = Form(...),  # Изменено на строку
    session: Session = Depends(db.get_db),
):
    """Validate scanned track numbers and return their details."""
    # Разделяем строку на список
    track_list = [t.strip().upper() for t in track_numbers.split(',') if t.strip()]
    
    results = []
    for track_num in track_list:
        track = crud.get_track_by_number(session, track_num)
        if track:
            results.append({
                "track_number": track.track_number,
                "status": track.status,
                "personal_code": track.personal_code,
                "found": True,
                "can_deliver": track.status in ["В Алматы (Склад)", "В Астане (Склад)"]
            })
        else:
            results.append({
                "track_number": track_num,
                "found": False,
                "error": "Track not found in system"
            })
    
    return {
        "total_scanned": len(track_list),
        "found": len([r for r in results if r.get("found")]),
        "not_found": len([r for r in results if not r.get("found")]),
        "results": results
    }


@app.post("/api/admin/scanner/deliver")
def deliver_scanned_parcels(
    track_numbers: str = Form(...),  # Изменено на строку
    session: Session = Depends(db.get_db),
):
    """Mark scanned parcels as delivered to client."""
    track_list = [t.strip().upper() for t in track_numbers.split(',') if t.strip()]
    
    delivered_count = 0
    errors = []
    
    for track_num in track_list:
        track = crud.get_track_by_number(session, track_num)
        if track:
            track.status = "Выдан клиенту"
            track.updated_at = datetime.datetime.utcnow()
            delivered_count += 1
        else:
            errors.append(f"{track_num}: not found")
    
    session.commit()
    
    return {
        "success": True,
        "delivered_count": delivered_count,
        "errors": errors
    }


@app.post("/api/admin/scanner/delete")
def delete_scanned_parcels(
    track_numbers: str = Form(...),  # Изменено на строку
    session: Session = Depends(db.get_db),
):
    """Permanently delete scanned parcels."""
    track_list = [t.strip().upper() for t in track_numbers.split(',') if t.strip()]
    
    deleted_count = 0
    errors = []
    
    for track_num in track_list:
        track = crud.get_track_by_number(session, track_num)
        if track:
            session.delete(track)
            deleted_count += 1
        else:
            errors.append(f"{track_num}: not found")
    
    session.commit()
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "errors": errors
    }


# =======================================================
# CALENDAR & BATCH UPDATE ENDPOINTS (NEW)
# =======================================================
@app.get("/api/admin/tracks-by-date")
def get_tracks_by_departure_date(
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Get all tracks grouped by departure date for calendar."""
    from sqlalchemy import func
    
    tracks = session.query(Track).filter(
        Track.departure_date.isnot(None)
    ).all()
    
    # Group by dates
    dates_dict = {}
    for track in tracks:
        date_str = track.departure_date.isoformat()
        if date_str not in dates_dict:
            dates_dict[date_str] = []
        dates_dict[date_str].append({
            'track_number': track.track_number,
            'status': track.status,
            'personal_code': track.personal_code,
            'is_assigned': track.personal_code is not None
        })
    
    # Format for calendar
    calendar_events = []
    for date_str, tracks_list in dates_dict.items():
        calendar_events.append({
            'date': date_str,
            'title': f"{len(tracks_list)} посылок",
            'count': len(tracks_list),
            'tracks': tracks_list
        })
    
    return calendar_events


@app.post("/api/admin/batch-update-status")
def batch_update_status_by_date(
    departure_date: str = Form(...),
    new_status: str = Form(...),
    session: Session = Depends(db.get_db),
    current_user: User = Depends(auth.require_admin)
):
    """Update status for all tracks from specific departure date."""
    try:
        dep_date = datetime.datetime.strptime(departure_date, "%Y-%m-%d").date()
        
        tracks = session.query(Track).filter(
            Track.departure_date == dep_date
        ).all()
        
        if not tracks:
            raise HTTPException(status_code=404, detail="No tracks found for this date")
        
        updated_count = 0
        for track in tracks:
            track.status = new_status
            track.updated_at = datetime.datetime.utcnow()
            updated_count += 1
        
        session.commit()
        
        crud.create_audit_log(
            session,
            action="batch_update_by_date",
            performed_by=current_user.email,
            target_entity="track",
            target_id=departure_date,
            details=f"Updated {updated_count} tracks to '{new_status}'"
        )
        
        return {
            "success": True,
            "updated_count": updated_count,
            "departure_date": departure_date,
            "new_status": new_status,
            "tracks": [t.track_number for t in tracks[:10]]
        }
    

        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
