# backend/init_db.py
"""
Initialize database with default admin user.
Run this script to create tables and add first admin.
"""

if __name__ == "__main__":
    from backend import db, models, crud
    
    # Initialize database
    print("[INIT] Initializing database...")
    db.initialize_database()
    
    # Create session
    session = db.SessionLocal()
    
    try:
        # Check if admin exists
        from backend.models import User
        existing_admin = session.query(User).filter(User.email == "admin@deltacargo.com").first()
        
        if not existing_admin:
            # Create default admin
            print("[INIT] Creating default admin user...")
            admin_user = crud.create_user(
                db=session,
                email="admin@deltacargo.com",
                password="admin123",
                name="Admin User",
                whatsapp="+77771234567",
                branch="HQ",
                personal_code="ADMIN001",
                role="admin"
            )
            print(f"[INIT] ✅ Admin created: {admin_user.email} / password: admin123")
            print(f"[INIT] ⚠️  CHANGE THIS PASSWORD AFTER FIRST LOGIN!")
        else:
            print("[INIT] ✅ Admin user already exists")
        
        # Create a test client (optional)
        test_client = session.query(User).filter(User.email == "client@test.com").first()
        if not test_client:
            print("[INIT] Creating test client user...")
            crud.create_user(
                db=session,
                email="client@test.com",
                password="test123",
                name="Test Client",
                whatsapp="+77757777777",
                branch="Almaty",
                role="client"
            )
            print("[INIT] ✅ Test client created: client@test.com / password: test123")
        
        print("[INIT] 🎉 Database initialization complete!")
        
    except Exception as e:
        print(f"[INIT] ❌ Error: {e}")
        session.rollback()
    finally:
        session.close()
