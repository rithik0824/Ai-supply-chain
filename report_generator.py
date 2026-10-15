"""
report_generator.py
Pulls together risk scores, inventory recommendations, and model outputs
into a single structured JSON report and a human-readable text summary.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

from data_loader import load_all
from risk_engine import risk_summary
from inventory_optimizer import inventory_summary

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):   return int(obj)
        if isinstance(obj, (np.floating,)):  return round(float(obj), 4)
        if isinstance(obj, (np.bool_,)):     return bool(obj)
        if isinstance(obj, pd.Timestamp):    return obj.isoformat()
        if pd.isna(obj):                     return None
        return super().default(obj)


def _top_n(df: pd.DataFrame, score_col: str, n: int = 5) -> list:
    return (
        df.sort_values(score_col, ascending=False)
        .head(n)
        .to_dict(orient="records")
    )


# ──────────────────────────────────────────────
# Report assembly
# ──────────────────────────────────────────────

def build_report(datasets: dict) -> dict:
    print("Building risk summary...")
    risks = risk_summary(datasets)

    print("Building inventory summary...")
    inv   = inventory_summary(datasets["inventory"])

    daily = risks["daily_risk"]
    latest_date = daily["date"].max()
    latest_row  = daily[daily["date"] == latest_date].iloc[0]

    # Current risk snapshot
    risk_snapshot = {
        "as_of_date":            str(datetime.now().date()),
        "composite_risk_score":  round(float(latest_row["composite_risk_score"]), 2),
        "risk_level":            str(latest_row["risk_level"]),
        "weather_score":         round(float(latest_row.get("weather_score", 0)), 2),
        "logistics_score":       round(float(latest_row.get("logistics_score", 0)), 2),
        "shipment_score":        round(float(latest_row.get("shipment_score", 0)), 2),
    }

    # Rolling 7-day trend
    recent = daily.sort_values("date").tail(7)
    trend = {
        "dates":  [str(d.date()) for d in recent["date"]],
        "scores": [round(float(s), 2) for s in recent["composite_risk_score"]],
        "levels": [str(l) for l in recent["risk_level"]],
    }

    # High-risk weather locations
    top_weather = _top_n(risks["weather_risk"], "weather_score")

    # High-risk logistics carriers
    top_logistics = _top_n(risks["logistics_risk"], "logistics_score")

    # High-risk shipment routes
    top_shipments = _top_n(risks["shipment_risk"], "shipment_score")

    # Top risky vendors
    top_vendors = _top_n(risks["delivery_risk"], "delivery_score")

    # Inventory recommendations (critical only, top 20)
    critical_inv = (
        inv["recommendations"][
            inv["recommendations"]["action"].isin(["CRITICAL", "REORDER"])
        ]
        [["Store ID", "Product ID", "Category", "Inventory Level",
          "reorder_point", "days_of_supply", "suggested_order_qty", "action"]]
        .head(20)
        .to_dict(orient="records")
    )

    # Executive summary text
    exec_summary = _exec_summary_text(risk_snapshot, inv, top_vendors)

    report = {
        "generated_at":        datetime.now().isoformat(),
        "executive_summary":   exec_summary,
        "risk_snapshot":       risk_snapshot,
        "risk_trend_7d":       trend,
        "top_weather_risks":   top_weather,
        "top_logistics_risks": top_logistics,
        "top_shipment_risks":  top_shipments,
        "top_vendor_risks":    top_vendors,
        "inventory": {
            "total_products":  inv["total_products"],
            "total_stores":    inv["total_stores"],
            "critical_items":  inv["critical_count"],
            "reorder_items":   inv["reorder_count"],
            "overstock_items": inv["overstock_count"],
            "ok_items":        inv["ok_count"],
            "critical_recommendations": critical_inv,
        },
    }
    return report


def _exec_summary_text(risk_snapshot: dict, inv: dict, top_vendors: list) -> str:
    level = risk_snapshot["risk_level"]
    score = risk_snapshot["composite_risk_score"]
    date  = risk_snapshot["as_of_date"]
    crit  = inv["critical_count"]
    reord = inv["reorder_count"]
    over  = inv["overstock_count"]

    vendor_names = ", ".join(v["Vendor"] for v in top_vendors[:3]) if top_vendors else "N/A"

    lines = [
        f"Supply Chain Risk Report — {date}",
        "=" * 50,
        f"Overall Risk Level : {level} (score: {score}/100)",
        "",
        "KEY FINDINGS:",
        f"  • Inventory: {crit} CRITICAL item(s) at stockout risk, "
        f"{reord} needing reorder, {over} overstocked.",
        f"  • Weather sub-score  : {risk_snapshot['weather_score']}/100",
        f"  • Logistics sub-score: {risk_snapshot['logistics_score']}/100",
        f"  • Shipment sub-score : {risk_snapshot['shipment_score']}/100",
        f"  • Top risky vendors  : {vendor_names}",
        "",
        "RECOMMENDED ACTIONS:",
    ]

    if level in ("High", "Critical"):
        lines += [
            "  1. Activate contingency supplier contacts immediately.",
            "  2. Expedite critical inventory replenishment orders.",
            "  3. Review carrier contracts in high-delay regions.",
        ]
    elif level == "Medium":
        lines += [
            "  1. Monitor weather forecasts for upcoming severe events.",
            "  2. Place reorder quantities for flagged inventory items.",
            "  3. Review vendor performance for late-delivery patterns.",
        ]
    else:
        lines += [
            "  1. Routine replenishment per EOQ recommendations.",
            "  2. Continue standard monitoring cadence.",
        ]

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Save outputs
# ──────────────────────────────────────────────

def save_report(report: dict) -> None:
    json_path = OUTPUT_DIR / "supply_chain_report.json"
    txt_path  = OUTPUT_DIR / "executive_summary.txt"
    csv_path  = OUTPUT_DIR / "critical_inventory.csv"

    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, cls=_Encoder)
    print(f"  JSON report  → {json_path}")

    with open(txt_path, "w") as f:
        f.write(report["executive_summary"])
    print(f"  Text summary → {txt_path}")

    crit = report["inventory"]["critical_recommendations"]
    if crit:
        pd.DataFrame(crit).to_csv(csv_path, index=False)
        print(f"  Critical CSV → {csv_path}")


if __name__ == "__main__":
    datasets = load_all()
    report   = build_report(datasets)
    save_report(report)

    print("\n" + report["executive_summary"])