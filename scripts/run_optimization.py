"""
Run Inventory Optimization — Phase 3

Reads ML predictions + sales history, computes EOQ/safety stock/ROP,
updates the inventory table, and prints a full alert report.

Run:  python scripts/run_optimization.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

from src.ml.inventory_optimizer import InventoryOptimizer
from src.config import settings


def main():
    optimizer = InventoryOptimizer(
        service_level=settings.DEFAULT_SERVICE_LEVEL,   # 0.95 = 95% service level
        lookback_days=90,                               # use last 90 days for demand stats
    )

    # Run optimization for all products
    all_metrics = optimizer.optimize_all()

    # Save alerts report to CSV
    alerts_df = optimizer.get_alerts_dataframe(all_metrics)
    os.makedirs("models", exist_ok=True)
    alerts_df.to_csv("models/inventory_alerts.csv", index=False)

    print("\n✓ Inventory alerts saved to models/inventory_alerts.csv")
    print("\nTop 10 products needing attention:")
    urgent = alerts_df[alerts_df["alert_level"].isin(["critical", "high", "medium"])]
    urgent = urgent.sort_values("stockout_risk_pct", ascending=False)
    print(urgent[[
        "product_name", "current_stock", "days_remaining",
        "reorder_point", "eoq", "alert_level", "stockout_risk_pct"
    ]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()