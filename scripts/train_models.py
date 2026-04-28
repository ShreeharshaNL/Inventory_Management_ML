"""
Model Trainer — Phase 2

Orchestrates training for all 50 products:
  1. Load and preprocess data from DB
  2. Train XGBoost (primary model)
  3. Train SARIMA (baseline)
  4. Compare models, pick winner
  5. Save predictions to DB
  6. Log everything to MLflow

Run:  python scripts/train_models.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import pandas as pd
import numpy as np
from datetime import datetime

from src.ml.preprocessing import DataPreprocessor, PreprocessingConfig
from src.ml.xgboost_model import XGBoostForecaster, XGBoostConfig
from src.ml.sarima_model import SARIMAForecaster
from src.api.database import get_db_context
from src.api.models import Product, Prediction, ModelRun

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def load_sales_data(db) -> pd.DataFrame:
    """Load all sales from DB into a DataFrame."""
    from src.api.models import Sale
    records = db.query(Sale).all()
    return pd.DataFrame([{
        "product_id":       r.product_id,
        "date":             r.date,
        "quantity_sold":    r.quantity_sold,
        "revenue":          r.revenue,
        "is_holiday":       r.is_holiday,
        "promotion_active": r.promotion_active,
    } for r in records])


def train_all_products(
    max_products: int = None,
    train_sarima: bool = False,   # SARIMA is slow — set True when you have time
) -> pd.DataFrame:
    """
    Train forecasting models for all products.

    Args:
        max_products: limit number of products (useful for testing)
        train_sarima: also train SARIMA baseline (slow, ~2 min/product)

    Returns:
        DataFrame summarizing results for all products
    """
    results = []

    with get_db_context() as db:
        # ── Load & Preprocess ─────────────────────────────────────────────────
        logger.info("Loading sales data from database...")
        df_raw = load_sales_data(db)
        logger.info(f"Loaded {len(df_raw):,} sales records for "
                    f"{df_raw['product_id'].nunique()} products.")

        preprocessor = DataPreprocessor(PreprocessingConfig(
            lag_days=[7, 14, 21, 30],
            rolling_windows=[7, 14, 30],
            test_split_days=60,
            min_history_days=60,
        ))
        df_processed = preprocessor.process(df_raw)
        logger.info(f"Preprocessing done: {len(df_processed):,} rows, "
                    f"{len(df_processed.columns)} columns.")

        # ── Get product list ──────────────────────────────────────────────────
        products = db.query(Product).filter(Product.is_active == True).all()
        if max_products:
            products = products[:max_products]

        logger.info(f"Training models for {len(products)} products...")

        for i, product in enumerate(products):
            pid = product.id
            logger.info(f"\n[{i+1}/{len(products)}] Product {pid}: {product.name}")

            result = {"product_id": pid, "product_name": product.name}

            # ── XGBoost ───────────────────────────────────────────────────────
            try:
                xgb = XGBoostForecaster(
                    product_id=pid,
                    config=XGBoostConfig(n_estimators=300, n_cv_splits=3)
                )
                xgb_metrics = xgb.train(df_processed, mlflow_run=False)
                result["xgb_mae"]  = xgb_metrics["mae"]
                result["xgb_rmse"] = xgb_metrics["rmse"]
                result["xgb_mape"] = xgb_metrics["mape"]
                result["xgb_status"] = "success"

                # ── Generate 30-day forecast & save to DB ─────────────────────
                forecast_df = xgb.predict_next_n_days(df_processed, n_days=30)
                _save_predictions_to_db(db, pid, forecast_df, model_name="xgboost")

                logger.info(f"  XGBoost MAPE: {xgb_metrics['mape']:.2f}%")

            except Exception as e:
                logger.error(f"  XGBoost failed: {e}")
                result["xgb_status"] = f"failed: {e}"

            # ── SARIMA (optional) ─────────────────────────────────────────────
            if train_sarima:
                try:
                    sarima = SARIMAForecaster(product_id=pid)
                    sarima_metrics = sarima.train(df_processed)
                    result["sarima_mae"]  = sarima_metrics["mae"]
                    result["sarima_rmse"] = sarima_metrics["rmse"]
                    result["sarima_mape"] = sarima_metrics["mape"]
                    result["sarima_status"] = "success"
                    logger.info(f"  SARIMA  MAPE: {sarima_metrics['mape']:.2f}%")

                    # Compare & pick winner
                    if sarima_metrics["mape"] < xgb_metrics.get("mape", 999):
                        result["winner"] = "sarima"
                        logger.info(f"  Winner: SARIMA 🏆")
                    else:
                        result["winner"] = "xgboost"
                        logger.info(f"  Winner: XGBoost 🏆")

                except Exception as e:
                    logger.error(f"  SARIMA failed: {e}")
                    result["sarima_status"] = f"failed: {e}"
            else:
                result["winner"] = "xgboost"

            results.append(result)

    results_df = pd.DataFrame(results)

    # ── Summary ───────────────────────────────────────────────────────────────
    successful = results_df[results_df["xgb_status"] == "success"]
    if len(successful) > 0:
        logger.info(f"\n{'='*50}")
        logger.info(f"TRAINING COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"Products trained: {len(successful)}/{len(results_df)}")
        logger.info(f"Avg MAPE:  {successful['xgb_mape'].mean():.2f}%")
        logger.info(f"Avg MAE:   {successful['xgb_mae'].mean():.2f}")
        logger.info(f"Best MAPE: {successful['xgb_mape'].min():.2f}% "
                    f"(product {successful.loc[successful['xgb_mape'].idxmin(), 'product_id']})")
        logger.info(f"Worst MAPE: {successful['xgb_mape'].max():.2f}% "
                    f"(product {successful.loc[successful['xgb_mape'].idxmax(), 'product_id']})")

    # Save results CSV
    results_df.to_csv("models/training_results.csv", index=False)
    logger.info("Results saved to models/training_results.csv")

    return results_df


def _save_predictions_to_db(db, product_id: int, forecast_df: pd.DataFrame, model_name: str):
    """Upsert predictions into the predictions table."""
    # Delete existing future predictions for this product
    from sqlalchemy import and_
    from datetime import date
    db.query(Prediction).filter(
        and_(
            Prediction.product_id == product_id,
            Prediction.forecast_date >= date.today(),
            Prediction.model_name == model_name,
        )
    ).delete()

    for _, row in forecast_df.iterrows():
        pred = Prediction(
            product_id=product_id,
            forecast_date=row["date"],
            predicted_demand=row["predicted_demand"],
            lower_bound=row.get("lower_bound"),
            upper_bound=row.get("upper_bound"),
            model_name=model_name,
            model_version="1.0",
        )
        db.add(pred)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-products", type=int, default=None,
                        help="Limit products to train (default: all 50)")
    parser.add_argument("--sarima", action="store_true",
                        help="Also train SARIMA baseline (slow)")
    args = parser.parse_args()

    train_all_products(
        max_products=args.max_products,
        train_sarima=args.sarima,
    )