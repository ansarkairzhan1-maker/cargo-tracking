# backend/init_db.py
from backend.db import Base, engine, SessionLocal, initialize_database
from backend.models import User
from backend.auth import hash_password
import backend.models


def init_db():
    # Initialize database connection
    engine, SessionLocal = initialize_database()
    
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Tables dropped.")
    
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")
    
    db = SessionLocal()
    try:
        # Create admin user
        print("Creating admin user...")
        admin = db.query(User).filter(User.email == "admin@deltacargo.com").first()
        if not admin:
            admin = User(
                email="admin@deltacargo.com",
                hashed_password=hash_password("admin123"),
                name="Admin User",
                personal_code="ADMIN",
                whatsapp="999999999",
                branch="Main Office",
                role="admin",
                is_active=True
            )
            db.add(admin)
            print("Admin user created. Email: admin@deltacargo.com, Password: admin123")
        
        # Create test client user
        print("Creating test client user...")
        client = db.query(User).filter(User.email == "client@test.com").first()
        if not client:
            client = User(
                email="client@test.com",
                hashed_password=hash_password("client123"),
                name="Test Client",
                personal_code="106",
                whatsapp="12345",
                branch="Test Branch",
                role="client",
                is_active=True
            )
            db.add(client)
            print("Test client created. Email: client@test.com, Password: client123, Code: 106")
        
        db.commit()
        print("Database initialization complete!")
        
    except Exception as e:
        print(f"Error during initialization: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
