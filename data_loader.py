"""
data_loader.py
Loads, cleans, and merges all 7 source datasets into unified DataFrames
ready for the prediction and scoring modules.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "datasets"
DB_PATH = BASE_DIR / "supply_chain.db"


# ──────────────────────────────────────────────
# Individual loaders
# ──────────────────────────────────────────────

def _require_db() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"SQLite DB not found at {DB_PATH}. Run: python import_datasets_to_db.py"
        )


def _read_table(table_name: str) -> pd.DataFrame:
    _require_db()
    with sqlite3.connect(DB_PATH) as conn:
        # Read entire table; datasets are relatively small except inventory.
        # If performance becomes an issue we can chunk/stream later.
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


def load_sales() -> pd.DataFrame:
    """medium_sales_dataset.csv — item-level outlet sales (1 000 rows)."""
    df = _read_table("medium_sales_dataset")
    df.columns = df.columns.str.strip()
    df["Item_MRP"] = pd.to_numeric(df["Item_MRP"], errors="coerce")
    df["Item_Outlet_Sales"] = pd.to_numeric(df["Item_Outlet_Sales"], errors="coerce")
    df["Outlet_Establishment_Year"] = pd.to_numeric(
        df["Outlet_Establishment_Year"], errors="coerce"
    )
    df["outlet_age_years"] = 2024 - df["Outlet_Establishment_Year"]
    return df


def load_inventory() -> pd.DataFrame:
    """retail_store_inventory.csv — daily store × product inventory (73 k rows)."""
    df = _read_table("retail_store_inventory")
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in [
        "Inventory Level",
        "Units Sold",
        "Units Ordered",
        "Demand Forecast",
        "Price",
        "Discount",
        "Competitor Pricing",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Days-of-supply: how many days current stock covers at current sales rate
    df["days_of_supply"] = np.where(
        df["Units Sold"] > 0,
        df["Inventory Level"] / df["Units Sold"],
        np.nan,
    )
    # Stockout flag: inventory below 20 % of demand forecast
    df["stockout_risk"] = (
        df["Inventory Level"] < 0.2 * df["Demand Forecast"]
    ).astype(int)
    # Over-stock flag: inventory above 3× demand forecast
    df["overstock_risk"] = (
        df["Inventory Level"] > 3 * df["Demand Forecast"]
    ).astype(int)
    return df


def load_deliveries() -> pd.DataFrame:
    """SCMS_Delivery_History_Dataset.csv — global procurement deliveries."""
    df = _read_table("scms_delivery_history_dataset")
    df.columns = df.columns.str.strip()
    date_cols = [
        "PQ First Sent to Client Date",
        "PO Sent to Vendor Date",
        "Scheduled Delivery Date",
        "Delivered to Client Date",
        "Delivery Recorded Date",
    ]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    # Delivery delay in days (positive = late)
    if "Scheduled Delivery Date" in df.columns and "Delivered to Client Date" in df.columns:
        df["delivery_delay_days"] = (
            df["Delivered to Client Date"] - df["Scheduled Delivery Date"]
        ).dt.days
        df["is_late"] = (df["delivery_delay_days"] > 0).astype(int)

    for col in ["Freight Cost (USD)", "Line Item Value", "Weight (Kilograms)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_weather() -> pd.DataFrame:
    """weather_data.csv — hourly weather by location (1 M rows → daily agg)."""
    df = _read_table("weather_data")
    df.columns = df.columns.str.strip()
    df["Date_Time"] = pd.to_datetime(df["Date_Time"], errors="coerce")
    df["date"] = df["Date_Time"].dt.date
    for col in ["Temperature_C", "Humidity_pct", "Precipitation_mm", "Wind_Speed_kmh"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Aggregate to daily level to keep downstream manageable
    daily = (
        df.groupby(["Location", "date"])
        .agg(
            temp_avg=("Temperature_C", "mean"),
            humidity_avg=("Humidity_pct", "mean"),
            precip_total=("Precipitation_mm", "sum"),
            wind_max=("Wind_Speed_kmh", "max"),
        )
        .reset_index()
    )
    daily["date"] = pd.to_datetime(daily["date"])

    # Severe-weather flag: heavy rain (>15 mm/day) OR high wind (>60 km/h)
    daily["severe_weather"] = (
        (daily["precip_total"] > 15) | (daily["wind_max"] > 60)
    ).astype(int)
    return daily


def load_customers() -> pd.DataFrame:
    """customer.csv — customer orders and satisfaction (751 rows)."""
    df = _read_table("customer")
    df.columns = df.columns.str.strip()
    for col in ["acquisition_date", "order_date", "payment_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in [
        "acquisition_cost_usd",
        "order_value_usd",
        "satisfaction_score",
        "support_tickets",
        "lead_time_days",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Payment delay: days between order and payment
    df["payment_delay_days"] = (
        df["payment_date"] - df["order_date"]
    ).dt.days
    return df


def load_logistics() -> pd.DataFrame:
    """logistics_performance.csv — carrier KPIs by region/date (99 rows)."""
    df = _read_table("logistics_performance")
    df.columns = df.columns.str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in [
        "shipments_processed",
        "delay_hours_avg",
        "fuel_price_usd_per_barrel",
        "warehouse_utilization_percent",
        "damage_claims_count",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Disruption flag: avg delay > 4 h OR warehouse util > 90 %
    df["logistics_disruption"] = (
        (df["delay_hours_avg"] > 4)
        | (df["warehouse_utilization_percent"] > 90)
    ).astype(int)
    return df


def load_shipments() -> pd.DataFrame:
    """shipment.csv — individual shipment records with status (727 rows)."""
    df = _read_table("shipment")
    df.columns = df.columns.str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ["value", "freight_cost", "customs_clearance_time_days"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["is_delayed"] = (df["delivery_status"] != "On-Time").astype(int)
    df["freight_pct_value"] = df["freight_cost"] / df["value"].replace(0, np.nan)
    return df


# ──────────────────────────────────────────────
# Master load function
# ──────────────────────────────────────────────

def load_all() -> dict:
    """Load all datasets and return them as a named dict."""
    print("Loading datasets...")
    datasets = {
        "sales":      load_sales(),
        "inventory":  load_inventory(),
        "deliveries": load_deliveries(),
        "weather":    load_weather(),
        "customers":  load_customers(),
        "logistics":  load_logistics(),
        "shipments":  load_shipments(),
    }
    for name, df in datasets.items():
        print(f"  {name:12s}: {len(df):>7,} rows × {df.shape[1]} cols")
    return datasets


if __name__ == "__main__":
    datasets = load_all()
    print("\nAll datasets loaded successfully.")