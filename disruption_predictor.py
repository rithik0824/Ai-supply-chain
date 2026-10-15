"""
disruption_predictor.py
Trains a Random Forest classifier to predict supply chain disruptions
and a Random Forest regressor to predict lead-time delays.
Uses shipments, logistics, weather, and customer data.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    classification_report, roc_auc_score,
    mean_absolute_error, r2_score,
)
import joblib
from pathlib import Path
from data_loader import load_all

MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────
# Feature engineering
# ──────────────────────────────────────────────

def build_disruption_features(datasets: dict) -> pd.DataFrame:
    """
    Build a shipment-level feature matrix for disruption classification.
    Target: is_delayed (binary)
    """
    ships = datasets["shipments"].copy()
    weather = datasets["weather"].copy()
    logistics = datasets["logistics"].copy()

    # Daily average weather risk per date
    w_daily = (
        weather.groupby("date")
        .agg(precip=("precip_total", "mean"), wind=("wind_max", "mean"),
             severe=("severe_weather", "sum"))
        .reset_index()
    )
    w_daily["date"] = pd.to_datetime(w_daily["date"])

    # Daily average logistics metrics
    l_daily = (
        logistics.groupby("date")
        .agg(delay_h=("delay_hours_avg", "mean"),
             wh_util=("warehouse_utilization_percent", "mean"),
             fuel=("fuel_price_usd_per_barrel", "mean"))
        .reset_index()
    )

    ships["date"] = pd.to_datetime(ships["date"])
    df = ships.merge(w_daily, on="date", how="left")
    df = df.merge(l_daily, on="date", how="left")

    # Encode categoricals
    le = LabelEncoder()
    df["type_enc"]     = le.fit_transform(df["type"].fillna("Unknown"))
    df["cat_enc"]      = le.fit_transform(df["product_category"].fillna("Unknown"))
    df["o_country_enc"]= le.fit_transform(df["O_Country"].fillna("Unknown"))
    df["d_country_enc"]= le.fit_transform(df["D_Country"].fillna("Unknown"))

    # Fill missing weather / logistics with neutral values
    df["precip"]  = df["precip"].fillna(df["precip"].median())
    df["wind"]    = df["wind"].fillna(df["wind"].median())
    df["severe"]  = df["severe"].fillna(0)
    df["delay_h"] = df["delay_h"].fillna(df["delay_h"].median())
    df["wh_util"] = df["wh_util"].fillna(df["wh_util"].median())
    df["fuel"]    = df["fuel"].fillna(df["fuel"].median())

    features = [
        "type_enc", "cat_enc", "o_country_enc", "d_country_enc",
        "value", "freight_cost", "freight_pct_value",
        "customs_clearance_time_days",
        "precip", "wind", "severe",
        "delay_h", "wh_util", "fuel",
    ]
    df["value"]              = df["value"].fillna(df["value"].median())
    df["freight_cost"]       = df["freight_cost"].fillna(df["freight_cost"].median())
    df["freight_pct_value"]  = df["freight_pct_value"].fillna(df["freight_pct_value"].median())
    df["customs_clearance_time_days"] = df["customs_clearance_time_days"].fillna(
        df["customs_clearance_time_days"].median()
    )

    return df[features + ["is_delayed", "shipment_id", "date"]].dropna(subset=["is_delayed"])


def build_leadtime_features(datasets: dict) -> pd.DataFrame:
    """
    Build a customer-order-level feature matrix for lead-time regression.
    Target: lead_time_days (continuous)
    """
    cust = datasets["customers"].copy()
    ships = datasets["shipments"].copy()

    # Merge on order date proximity (weekly average freight cost as proxy)
    ships["week"] = ships["date"].dt.to_period("W")
    cust["week"]  = cust["order_date"].dt.to_period("W")
    ship_weekly = (
        ships.groupby("week")
        .agg(avg_customs=("customs_clearance_time_days", "mean"),
             delay_rate=("is_delayed", "mean"),
             avg_freight=("freight_cost", "mean"))
        .reset_index()
    )
    df = cust.merge(ship_weekly, on="week", how="left")

    le = LabelEncoder()
    df["segment_enc"] = le.fit_transform(df["market_segment"].fillna("Unknown"))
    df["supplier_enc"] = le.fit_transform(df["supplier_id"].fillna("Unknown"))

    for col in ["avg_customs", "delay_rate", "avg_freight"]:
        df[col] = df[col].fillna(df[col].median())

    features = [
        "segment_enc", "supplier_enc",
        "order_value_usd", "acquisition_cost_usd",
        "satisfaction_score", "support_tickets",
        "payment_delay_days",
        "avg_customs", "delay_rate", "avg_freight",
    ]
    df["order_value_usd"]      = df["order_value_usd"].fillna(df["order_value_usd"].median())
    df["acquisition_cost_usd"] = df["acquisition_cost_usd"].fillna(df["acquisition_cost_usd"].median())
    df["payment_delay_days"]   = df["payment_delay_days"].fillna(0)

    return df[features + ["lead_time_days"]].dropna(subset=["lead_time_days"])


# ──────────────────────────────────────────────
# Model training
# ──────────────────────────────────────────────

def train_disruption_classifier(datasets: dict) -> dict:
    """Train and evaluate a disruption classification model."""
    print("\n[Disruption Classifier]")
    data = build_disruption_features(datasets)
    feature_cols = [c for c in data.columns if c not in ["is_delayed", "shipment_id", "date"]]

    X = data[feature_cols]
    y = data["is_delayed"]

    print(f"  Dataset: {len(X)} samples, class balance: {y.mean():.2%} delayed")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    sample_weights = compute_sample_weight(class_weight="balanced", y=y_train)
    model = HistGradientBoostingClassifier(
        max_iter=300, max_depth=8, min_samples_leaf=5,
        learning_rate=0.05, random_state=42
    )
    model.fit(X_train, y_train, sample_weight=sample_weights)

    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print(classification_report(y_test, y_pred, target_names=["On-Time", "Delayed"]))
    try:
        auc = roc_auc_score(y_test, y_proba)
        print(f"  ROC-AUC: {auc:.4f}")
    except Exception:
        pass

    # Feature importances using permutation importance
    perm_result = permutation_importance(model, X_test, y_test, n_repeats=5, random_state=42)
    importances = pd.Series(perm_result.importances_mean, index=feature_cols)
    print("\n  Top 5 features:")
    print(importances.sort_values(ascending=False).head(5).to_string())

    # Save model
    joblib.dump(model, MODEL_DIR / "disruption_classifier.pkl")
    print(f"\n  Model saved → {MODEL_DIR}/disruption_classifier.pkl")

    return {
        "model": model,
        "feature_cols": feature_cols,
        "test_data": (X_test, y_test, y_proba),
        "importances": importances,
    }


def train_leadtime_regressor(datasets: dict) -> dict:
    """Train and evaluate a lead-time regression model."""
    print("\n[Lead-Time Regressor]")
    data = build_leadtime_features(datasets)
    feature_cols = [c for c in data.columns if c != "lead_time_days"]

    X = data[feature_cols]
    y = data["lead_time_days"]

    print(f"  Dataset: {len(X)} samples, mean lead time: {y.mean():.1f} days")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=100, max_depth=8, min_samples_leaf=3,
        random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2  = r2_score(y_test, y_pred)
    print(f"  MAE: {mae:.2f} days   R²: {r2:.4f}")

    importances = pd.Series(model.feature_importances_, index=feature_cols)
    print("\n  Top 5 features:")
    print(importances.sort_values(ascending=False).head(5).to_string())

    joblib.dump(model, MODEL_DIR / "leadtime_regressor.pkl")
    print(f"\n  Model saved → {MODEL_DIR}/leadtime_regressor.pkl")

    return {
        "model": model,
        "feature_cols": feature_cols,
        "mae": mae,
        "r2": r2,
        "importances": importances,
    }


# ──────────────────────────────────────────────
# Inference helpers
# ──────────────────────────────────────────────

def predict_disruption(shipment_features: pd.DataFrame) -> np.ndarray:
    """Load saved model and return disruption probability for new rows."""
    model = joblib.load(MODEL_DIR / "disruption_classifier.pkl")
    return model.predict_proba(shipment_features)[:, 1]


def predict_leadtime(order_features: pd.DataFrame) -> np.ndarray:
    """Load saved model and return predicted lead time in days."""
    model = joblib.load(MODEL_DIR / "leadtime_regressor.pkl")
    return model.predict(order_features)


if __name__ == "__main__":
    datasets = load_all()
    clf_result = train_disruption_classifier(datasets)
    reg_result = train_leadtime_regressor(datasets)
    print("\nAll models trained and saved.")