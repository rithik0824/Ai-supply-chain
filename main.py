"""
main.py
Master pipeline — run this to execute the full system end-to-end:
  1. Load & preprocess all datasets
  2. Compute risk scores
  3. Optimise inventory
  4. Train prediction models
  5. Generate report
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from data_loader        import load_all
from risk_engine        import risk_summary
from inventory_optimizer import inventory_summary
from disruption_predictor import train_disruption_classifier, train_leadtime_regressor
from report_generator   import build_report, save_report


def run_pipeline(train_models: bool = True):
    print("=" * 60)
    print("  AI Supply Chain Disruption Prediction System")
    print("=" * 60)

    # 1. Load data
    print("\n[1/5] Loading datasets")
    datasets = load_all()

    # 2. Risk scoring
    print("\n[2/5] Computing risk scores")
    risks = risk_summary(datasets)
    daily = risks["daily_risk"]
    print(f"  Daily risk computed for {len(daily)} dates")
    print(f"  Risk level distribution:")
    print(daily["risk_level"].value_counts().to_string(header=False))

    # 3. Inventory optimisation
    print("\n[3/5] Optimising inventory")
    inv = inventory_summary(datasets["inventory"])
    print(f"  Products analysed : {inv['total_products']}")
    print(f"  CRITICAL          : {inv['critical_count']}")
    print(f"  REORDER           : {inv['reorder_count']}")
    print(f"  OVERSTOCK         : {inv['overstock_count']}")
    print(f"  OK                : {inv['ok_count']}")

    # 4. Train models
    if train_models:
        print("\n[4/5] Training prediction models")
        clf = train_disruption_classifier(datasets)
        reg = train_leadtime_regressor(datasets)
    else:
        print("\n[4/5] Skipping model training (train_models=False)")

    # 5. Generate report
    print("\n[5/5] Generating report")
    report = build_report(datasets)
    save_report(report)

    print("\n" + "=" * 60)
    print("  Pipeline complete.")
    print("=" * 60)
    print("\n" + report["executive_summary"])

    return report


if __name__ == "__main__":
    run_pipeline(train_models=True)