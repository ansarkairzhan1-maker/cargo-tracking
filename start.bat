BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # This is C:\...\cargo\backend
PROJECT_DIR = os.path.dirname(BASE_DIR)              # This is C:\...\cargo
FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend") # This is C:\...\cargo\frontend
FRONTEND_SRC_DIR = os.path.join(FRONTEND_DIR, "src") # This is C:\...\cargo\frontend\src

app.mount("/static", StaticFiles(directory=FRONTEND_SRC_DIR), name="static")

@app.get("/admin")
def admin_page():
    path = os.path.join(FRONTEND_DIR, "admin.html")
    # ... checks for file existence ...
    return FileResponse(path)
    
cd C:\Users\banit\Downloads\cargo\backend
uvicorn backend.main:app --reload
python -m backend.init_db

$env:DATABASE_URL="mysql+pymysql://freedb_kazkans:B72%23%24mh%25mSTje@sql.freedb.tech:3306/freedb_cargotest"
uvicorn backend.main:app --reload

