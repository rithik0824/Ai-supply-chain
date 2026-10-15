# Classification: Public
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
from pathlib import Path
import sys

# Ensure the local directory is in the path so we can import from main
sys.path.insert(0, str(Path(__file__).parent))
from main import run_pipeline
import database
import auth

# Initialize the database (creates tables if they don't exist)
database.init_db()

app = FastAPI()

# Add CORS middleware for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_FILE = Path(__file__).parent / "output" / "supply_chain_report.json"

# --- Pydantic Models for Input/Output ---

class UserCreate(BaseModel):
    username: str
    password: str

class InventoryCreate(BaseModel):
    item_name: str
    current_stock: int
    demand_forecast: int
    stockout_risk: bool = False

# --- Auth Routes ---

@app.post("/api/auth/register")
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(database.User).filter(database.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = database.User(username=user.username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully"}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(database.User).filter(database.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Inventory Route (Read-Only from SQL) ---

@app.get("/api/inventory")
def get_inventory(current_user: database.User = Depends(auth.get_current_user)):
    import sqlite3

    db_path = Path(__file__).parent / "supply_chain.db"
    if not db_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"SQLite DB not found at {db_path}. Run: python import_datasets_to_db.py",
        )

    with sqlite3.connect(db_path) as conn:
        # Return a sample of 50 rows for UI performance
        df = pd.read_sql_query(
            "SELECT * FROM retail_store_inventory LIMIT 50",
            conn,
        )

    items = []
    for idx, row in df.iterrows():
        items.append(
            {
                "id": int(idx),
                "item_name": f"{row['Product ID']} ({row['Category']})",
                "current_stock": int(row["Inventory Level"]),
                "demand_forecast": int(row["Demand Forecast"]),
                "stockout_risk": int(row["Inventory Level"]) < 0.2 * int(
                    row["Demand Forecast"]
                ),
            }
        )
    return items


# --- ML Pipeline Routes (Protected) ---

@app.get("/api/auth/me")
def auth_me(current_user: database.User = Depends(auth.get_current_user)):
    # Return currently logged-in user's public info
    return {"username": current_user.username}

@app.get("/api/report")
async def get_report(current_user: database.User = Depends(auth.get_current_user)):
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    else:
        raise HTTPException(status_code=404, detail="Report not found. Please run the pipeline first.")

@app.post("/api/run")
async def run_system(current_user: database.User = Depends(auth.get_current_user)):
    try:
        # Run the pipeline (this may take several seconds)
        run_pipeline(train_models=True)
        
        # Read the newly generated report
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE, "r") as f:
                data = json.load(f)
            return JSONResponse(content={"message": "Pipeline completed successfully", "report": data})
        else:
            raise HTTPException(status_code=500, detail="Pipeline ran, but report was not generated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount the frontend directory to serve the UI
# Check if frontend/dist exists, otherwise mount frontend_old or fail gracefully
import os
if os.path.exists(str(Path(__file__).parent / "frontend" / "dist")):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
else:
    print("Warning: frontend/dist not found. The UI will not be served.")
