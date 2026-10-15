"""
inventory_optimizer.py
Computes reorder points, safety stock, EOQ, and generates
replenishment recommendations from the retail inventory dataset.
"""

import pandas as pd
import numpy as np
from data_loader import load_inventory


# ──────────────────────────────────────────────
# Statistical helpers
# ──────────────────────────────────────────────

Z_SCORES = {
    0.90: 1.28,
    0.95: 1.645,
    0.99: 2.326,
}

HOLDING_COST_RATE   = 0.20   # 20% of unit cost per year
ORDERING_COST       = 50.0   # fixed cost per order (USD)
SERVICE_LEVEL       = 0.95   # default 95% service level
LEAD_TIME_DAYS      = 3      # assumed replenishment lead time (days)

# Inventory-vs-forecast thresholds (calibrated to dataset's replenishment cadence)
CRITICAL_RATIO  = 0.5   # stock < 50% of forecast → CRITICAL
REORDER_RATIO   = 1.0   # stock < 100% of forecast → REORDER
OVERSTOCK_RATIO = 4.0   # stock > 400% of forecast → OVERSTOCK


def _daily_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per product × store: mean and std of daily demand (units sold),
    plus average price and inventory level.
    """
    stats = (
        df.groupby(["Store ID", "Product ID", "Category"])
        .agg(
            mean_demand=("Units Sold", "mean"),
            std_demand=("Units Sold", "std"),
            mean_inventory=("Inventory Level", "mean"),
            mean_price=("Price", "mean"),
            demand_forecast_avg=("Demand Forecast", "mean"),
            total_days=("Units Sold", "count"),
        )
        .reset_index()
    )
    stats["std_demand"] = stats["std_demand"].fillna(0)
    return stats


def safety_stock(stats: pd.DataFrame, service_level: float = SERVICE_LEVEL,
                 lead_time: int = LEAD_TIME_DAYS) -> pd.DataFrame:
    """
    Safety stock = Z × σ_demand × √(lead_time)
    """
    z = Z_SCORES.get(service_level, 1.645)
    stats = stats.copy()
    stats["safety_stock"] = (z * stats["std_demand"] * np.sqrt(lead_time)).round(1)
    return stats


def reorder_point(stats: pd.DataFrame, lead_time: int = LEAD_TIME_DAYS) -> pd.DataFrame:
    """
    Reorder point (ROP) = mean_demand × lead_time + safety_stock
    """
    stats = stats.copy()
    stats["reorder_point"] = (
        stats["mean_demand"] * lead_time + stats["safety_stock"]
    ).round(1)
    return stats


def economic_order_quantity(stats: pd.DataFrame,
                             ordering_cost: float = ORDERING_COST,
                             holding_rate: float = HOLDING_COST_RATE) -> pd.DataFrame:
    """
    EOQ = √(2 × D × S / H)
    D = annual demand, S = ordering cost, H = annual holding cost per unit
    """
    stats = stats.copy()
    annual_demand = stats["mean_demand"] * 365
    holding_cost  = stats["mean_price"] * holding_rate
    stats["eoq"] = np.sqrt(
        2 * annual_demand * ordering_cost / holding_cost.replace(0, np.nan)
    ).round(1)
    stats["eoq"] = stats["eoq"].fillna(0)
    return stats


def replenishment_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each product × store, flag whether action is needed TODAY:
      CRITICAL  — current inventory < reorder_point
      REORDER   — inventory within 20% above reorder_point
      OK        — adequate stock
      OVERSTOCK — inventory > 3× reorder_point
    Returns only rows where action != OK, sorted by urgency.
    """
    # Use most recent inventory snapshot per store × product
    latest = (
        df.sort_values("Date")
        .groupby(["Store ID", "Product ID"])
        .last()
        .reset_index()
    )

    stats = _daily_stats(df)
    stats = safety_stock(stats)
    stats = reorder_point(stats)
    stats = economic_order_quantity(stats)

    merged = latest.merge(
        stats[["Store ID", "Product ID", "mean_demand", "safety_stock",
               "reorder_point", "eoq", "mean_price"]],
        on=["Store ID", "Product ID"],
        how="left",
    )

    def _action(row):
        inv = row["Inventory Level"]
        forecast = row.get("demand_forecast_avg", row.get("Demand Forecast", 0))
        if forecast <= 0:
            return "OK"
        ratio = inv / forecast
        if ratio < CRITICAL_RATIO:
            return "CRITICAL"
        elif ratio < REORDER_RATIO:
            return "REORDER"
        elif ratio > OVERSTOCK_RATIO:
            return "OVERSTOCK"
        else:
            return "OK"

    merged["action"] = merged.apply(_action, axis=1)
    merged["suggested_order_qty"] = np.where(
        merged["action"].isin(["CRITICAL", "REORDER"]),
        merged["eoq"].fillna(0),
        0,
    ).round(0)
    merged["days_of_supply"] = np.where(
        merged["mean_demand"] > 0,
        (merged["Inventory Level"] / merged["mean_demand"]).round(1),
        np.nan,
    )
    merged["est_stockout_days"] = np.where(
        merged["action"].isin(["CRITICAL", "REORDER"]),
        merged["days_of_supply"],
        np.nan,
    )

    priority_order = {"CRITICAL": 0, "REORDER": 1, "OVERSTOCK": 2, "OK": 3}
    result = merged.copy()
    result["_priority"] = result["action"].map(priority_order)
    result = result.sort_values(["_priority", "est_stockout_days"]).drop("_priority", axis=1)

    return result


def inventory_summary(df: pd.DataFrame) -> dict:
    """High-level summary stats for reporting."""
    recs = replenishment_recommendations(df)
    action_counts = recs["action"].value_counts().to_dict()

    return {
        "recommendations": recs,
        "action_counts": action_counts,
        "critical_count": action_counts.get("CRITICAL", 0),
        "reorder_count":  action_counts.get("REORDER", 0),
        "overstock_count": action_counts.get("OVERSTOCK", 0),
        "ok_count":        action_counts.get("OK", 0),
        "total_products":  recs["Product ID"].nunique(),
        "total_stores":    recs["Store ID"].nunique(),
    }


if __name__ == "__main__":
    df = load_inventory()
    summary = inventory_summary(df)

    print("=== Inventory Summary ===")
    for k, v in summary.items():
        if k != "recommendations":
            print(f"  {k}: {v}")

    print("\n=== Top 10 Critical / Reorder Items ===")
    critical = summary["recommendations"][
        summary["recommendations"]["action"].isin(["CRITICAL", "REORDER"])
    ].head(10)
    cols = ["Store ID", "Product ID", "Category", "Inventory Level",
            "reorder_point", "days_of_supply", "suggested_order_qty", "action"]
    print(critical[cols].to_string(index=False))