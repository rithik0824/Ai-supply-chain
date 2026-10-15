"""
risk_engine.py
Computes a composite Supply Chain Risk Score (0-100) per day/region/route
by combining signals from weather, logistics, shipments, and deliveries.
"""

import pandas as pd
import numpy as np
from data_loader import load_all


# ──────────────────────────────────────────────
# Weight configuration  (must sum to 1.0)
# ──────────────────────────────────────────────
WEIGHTS = {
    "weather":    0.20,
    "logistics":  0.30,
    "shipment":   0.25,
    "delivery":   0.25,
}


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalise a series to [0, 1]; returns 0 if all values equal."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(0.0, index=series.index)
    return (series - mn) / (mx - mn)


# ──────────────────────────────────────────────
# Per-source risk sub-scores
# ──────────────────────────────────────────────

def weather_risk(weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily weather risk score per location.
    Drivers: precipitation, wind speed, severe_weather flag.
    """
    df = weather_df.copy()
    df["precip_score"] = _normalize(df["precip_total"])
    df["wind_score"]   = _normalize(df["wind_max"])
    df["weather_score"] = (
        0.4 * df["precip_score"]
        + 0.4 * df["wind_score"]
        + 0.2 * df["severe_weather"]
    ) * 100
    return df[["Location", "date", "weather_score", "severe_weather",
               "precip_total", "wind_max"]].rename(columns={"Location": "region"})


def logistics_risk(logistics_df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily logistics risk score per region/carrier.
    Drivers: delay hours, warehouse utilisation, fuel price, damage claims.
    """
    df = logistics_df.copy()
    df["delay_score"]    = _normalize(df["delay_hours_avg"])
    df["util_score"]     = _normalize(df["warehouse_utilization_percent"])
    df["fuel_score"]     = _normalize(df["fuel_price_usd_per_barrel"])
    df["damage_score"]   = _normalize(df["damage_claims_count"])
    df["logistics_score"] = (
        0.35 * df["delay_score"]
        + 0.30 * df["util_score"]
        + 0.20 * df["fuel_score"]
        + 0.15 * df["damage_score"]
    ) * 100
    return df[["date", "region", "carrier", "logistics_score",
               "logistics_disruption", "delay_hours_avg",
               "warehouse_utilization_percent", "fuel_price_usd_per_barrel"]]


def shipment_risk(shipments_df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily shipment risk score per origin country.
    Drivers: delay rate, customs clearance time, freight cost ratio.
    """
    df = shipments_df.copy()
    daily = (
        df.groupby(["date", "O_Country"])
        .agg(
            delay_rate=("is_delayed", "mean"),
            avg_customs=("customs_clearance_time_days", "mean"),
            avg_freight_pct=("freight_pct_value", "mean"),
            shipment_count=("shipment_id", "count"),
        )
        .reset_index()
    )
    daily["delay_score"]   = _normalize(daily["delay_rate"])
    daily["customs_score"] = _normalize(daily["avg_customs"])
    daily["freight_score"] = _normalize(daily["avg_freight_pct"])
    daily["shipment_score"] = (
        0.45 * daily["delay_score"]
        + 0.35 * daily["customs_score"]
        + 0.20 * daily["freight_score"]
    ) * 100
    return daily[["date", "O_Country", "shipment_score", "delay_rate",
                  "avg_customs", "shipment_count"]].rename(
        columns={"O_Country": "country"}
    )


def delivery_risk(deliveries_df: pd.DataFrame) -> pd.DataFrame:
    """
    Vendor-level delivery risk from SCMS history.
    Drivers: late rate, avg delay days, freight cost per kg.
    """
    df = deliveries_df.copy().dropna(subset=["Vendor"])
    df["freight_per_kg"] = df["Freight Cost (USD)"] / df["Weight (Kilograms)"].replace(0, np.nan)
    vendor = (
        df.groupby("Vendor")
        .agg(
            late_rate=("is_late", "mean"),
            avg_delay=("delivery_delay_days", "mean"),
            avg_freight_per_kg=("freight_per_kg", "mean"),
            shipment_count=("is_late", "count"),
        )
        .reset_index()
    )
    vendor["late_score"]    = _normalize(vendor["late_rate"])
    vendor["delay_score"]   = _normalize(vendor["avg_delay"].clip(lower=0))
    vendor["freight_score"] = _normalize(vendor["avg_freight_per_kg"])
    vendor["delivery_score"] = (
        0.50 * vendor["late_score"]
        + 0.30 * vendor["delay_score"]
        + 0.20 * vendor["freight_score"]
    ) * 100
    return vendor[["Vendor", "delivery_score", "late_rate",
                   "avg_delay", "shipment_count"]]


# ──────────────────────────────────────────────
# Composite risk score
# ──────────────────────────────────────────────

def composite_risk_by_date(
    weather_df, logistics_df, shipments_df
) -> pd.DataFrame:
    """
    Merge weather, logistics, and shipment risk into a single daily
    composite score (no vendor dimension needed for daily view).
    """
    w = weather_risk(weather_df)
    l = logistics_risk(logistics_df)
    s = shipment_risk(shipments_df)

    # Average weather score across locations per day
    w_daily = w.groupby("date")["weather_score"].mean().reset_index()

    # Average logistics score across regions per day
    l_daily = l.groupby("date")["logistics_score"].mean().reset_index()

    # Average shipment score across countries per day
    s_daily = s.groupby("date")["shipment_score"].mean().reset_index()

    merged = (
        w_daily
        .merge(l_daily, on="date", how="outer")
        .merge(s_daily, on="date", how="outer")
        .sort_values("date")
    )
    merged = merged.fillna(merged.mean(numeric_only=True))

    # Weighted composite
    w_wt = WEIGHTS["weather"]
    l_wt = WEIGHTS["logistics"]
    s_wt = WEIGHTS["shipment"]
    # delivery weight redistributed to the three available daily sources
    total = w_wt + l_wt + s_wt
    merged["composite_risk_score"] = (
        (w_wt / total) * merged["weather_score"]
        + (l_wt / total) * merged["logistics_score"]
        + (s_wt / total) * merged["shipment_score"]
    ).round(2)

    merged["risk_level"] = pd.cut(
        merged["composite_risk_score"],
        bins=[0, 30, 60, 80, 100],
        labels=["Low", "Medium", "High", "Critical"],
        include_lowest=True,
    )
    return merged


def risk_summary(datasets: dict) -> dict:
    """Compute all risk views and return as a dict of DataFrames."""
    weather_risk_df   = weather_risk(datasets["weather"])
    logistics_risk_df = logistics_risk(datasets["logistics"])
    shipment_risk_df  = shipment_risk(datasets["shipments"])
    delivery_risk_df  = delivery_risk(datasets["deliveries"])
    daily_risk_df     = composite_risk_by_date(
        datasets["weather"], datasets["logistics"], datasets["shipments"]
    )

    return {
        "weather_risk":   weather_risk_df,
        "logistics_risk": logistics_risk_df,
        "shipment_risk":  shipment_risk_df,
        "delivery_risk":  delivery_risk_df,
        "daily_risk":     daily_risk_df,
    }


if __name__ == "__main__":
    datasets = load_all()
    risks = risk_summary(datasets)

    print("\n=== Daily Composite Risk (sample) ===")
    print(risks["daily_risk"].tail(10).to_string(index=False))

    print("\n=== Top 10 High-Risk Vendors ===")
    top_vendors = risks["delivery_risk"].sort_values("delivery_score", ascending=False).head(10)
    print(top_vendors.to_string(index=False))

    print("\n=== Risk Level Distribution (daily) ===")
    print(risks["daily_risk"]["risk_level"].value_counts().to_string())