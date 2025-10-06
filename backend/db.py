# backend/db.py
"""
Database configuration module for Delta Cargo system.
Supports both SQLite (development) and PostgreSQL (production).
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use defaults

# Get database URL from environment variable or use SQLite default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cargo.db")

# Database engine configuration
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL configuration for production
    engine = create_engine(
        DATABASE_URL,
        echo=False,  # Set to True for SQL query logging
        pool_pre_ping=True,  # Test connections before using them
        pool_size=10,  # Number of connections to keep in pool
        max_overflow=20,  # Maximum number of connections to create beyond pool_size
        pool_recycle=3600,  # Recycle connections after 1 hour
    )
    print("[DB] Using PostgreSQL database")
    
elif DATABASE_URL.startswith("mysql"):
    # MySQL configuration (if needed)
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )
    print("[DB] Using MySQL database")
    
else:
    # SQLite configuration for development/local
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite
        poolclass=StaticPool,  # Use static pool for SQLite
        echo=False,  # Set to True for SQL query logging
    )
    
    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    print(f"[DB] Using SQLite database: {DATABASE_URL}")

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create declarative base for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    Use with FastAPI's Depends() for automatic session management.
    
    Example:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_database():
    """
    Initialize the database by creating all tables.
    Called at application startup.
    """
    from . import models  # Import models to register them
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("[DB] Database tables created/verified successfully")
        
        # Verify connection
        with engine.connect() as connection:
            print("[DB] Database connection verified")
            
    except Exception as e:
        print(f"[DB] Error initializing database: {e}")
        raise


def get_database_info():
    """
    Get information about the current database configuration.
    Useful for debugging and monitoring.
    
    Returns:
        dict: Database configuration details
    """
    db_type = "unknown"
    if DATABASE_URL.startswith("postgresql"):
        db_type = "PostgreSQL"
    elif DATABASE_URL.startswith("mysql"):
        db_type = "MySQL"
    elif DATABASE_URL.startswith("sqlite"):
        db_type = "SQLite"
    
    return {
        "type": db_type,
        "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        "pool_size": engine.pool.size() if hasattr(engine.pool, 'size') else "N/A",
        "echo": engine.echo,
    }


def close_database():
    """
    Close all database connections.
    Called at application shutdown.
    """
    try:
        engine.dispose()
        print("[DB] Database connections closed")
    except Exception as e:
        print(f"[DB] Error closing database: {e}")


# Health check function
def check_database_health():
    """
    Check if database is accessible and healthy.
    
    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"[DB] Health check failed: {e}")
        return False


# Export commonly used items
__all__ = [
    'engine',
    'SessionLocal',
    'Base',
    'get_db',
    'initialize_database',
    'close_database',
    'get_database_info',
    'check_database_health'
]
