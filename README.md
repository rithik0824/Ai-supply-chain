# AI Supply Chain Disruption Prediction System

This project is an end-to-end Machine Learning pipeline and full-stack web application designed to predict supply chain disruptions, optimize inventory, and compute daily risk scores. It takes in various datasets (sales, inventory, shipments, weather, logistics) and processes them to alert stakeholders of potential delays before they happen.

## System Overview

The system evaluates the supply chain from multiple angles:
1. **Risk Scoring:** Analyzes weather events, logistics delays, and shipment histories to generate a composite daily risk score out of 100.
2. **Inventory Optimization:** Classifies retail inventory into actionable statuses (`CRITICAL`, `REORDER`, `OVERSTOCK`, `OK`) based on real-time stock levels and demand forecasts.
3. **Disruption Prediction:** Utilizes advanced Gradient Boosting machine learning models to predict whether individual shipments will be delayed, and estimates the exact lead-time in days for customer orders.
4. **Interactive Dashboard:** Serves all of this data through a modern, web-based React single-page application powered by a FastAPI backend with JWT Authentication.

## Architecture and Modules

The project is broken down into modular Python scripts and a frontend web application:

### Backend (FastAPI / Machine Learning)
- **`data_loader.py`**: Handles loading, cleaning, and merging of all 7 raw datasets located in the `datasets/` directory.
- **`risk_engine.py`**: Computes sub-scores for weather risk, logistics risk, and vendor delivery risk, aggregating them into a single `composite_risk_score`.
- **`inventory_optimizer.py`**: Processes `retail_store_inventory.csv` to flag stockouts and recommend reorder points.
- **`disruption_predictor.py`**: Trains Machine Learning models to predict continuous order lead-times and binary shipment delays.
- **`report_generator.py`**: Aggregates findings from the risk engine, inventory optimizer, and ML models into a structured `supply_chain_report.json` and a human-readable `executive_summary.txt`.
- **`database.py` & `auth.py`**: Manages the SQLite database and handles secure JWT user authentication.
- **`api.py`**: The FastAPI server that acts as the bridge between the React frontend and the Python ML pipeline.

### Frontend (React / Vite)
- **`/frontend`**: A modern React application utilizing Vite, Lucide React, and React Router.
- **Authentication**: JWT-based login system for securing dashboard access.
- **Dashboard**: High-level KPIs mapping directly to the ML models' JSON outputs.
- **Inventory Page**: A comprehensive, read-only data table fetching records directly from the underlying retail CSV dataset.

## Installation and Setup

### 1. Backend Setup
Activate your virtual environment and install dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

Seed the default admin user:
```bash
python -c 'import database, auth; db=database.SessionLocal(); db.add(database.User(username="admin", password_hash=auth.get_password_hash("password"))); db.commit()'
```

Start the FastAPI backend:
```bash
uvicorn api:app --reload
```
The API will run on **http://127.0.0.1:8000**.

### 2. Frontend Setup
Open a new terminal window, navigate to the frontend directory, and install the Node dependencies:
```bash
cd frontend
npm install
npm run dev
```
The React UI will run on **http://localhost:5173**.

## Usage
1. Open the React application in your browser.
2. Log in using the default credentials:
   - **Username:** `admin`
   - **Password:** `password`
3. Click the **Run ML Pipeline** button on the dashboard to actively retrain the machine learning models on the backend and pull the latest generated insights.
4. View the **Inventory** page to browse through the raw dataset of items and check their forecasted stockout risk statuses.
