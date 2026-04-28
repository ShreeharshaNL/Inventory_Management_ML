"""
Model Evaluation Utilities — Phase 2

Tools for comparing model performance, generating evaluation reports,
and visualizing forecast accuracy. Used after training to assess model quality.
"""

import numpy as np
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def evaluate_forecast(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str = "model",
) -> dict:
    """
    Comprehensive forecast evaluation metrics.

    Returns:
        dict with MAE, RMSE, MAPE, bias, and coverage metrics
    """
    y_true = np.array(y_true, dtype=float)
    y_pred = np.clip(np.array(y_pred, dtype=float), 0, None)

    mae  = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    bias = float(np.mean(y_pred - y_true))  # positive = over-forecast

    mask = y_true != 0
    mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)

    # Forecast skill: how much better than naive (predict yesterday's demand)?
    naive_pred = np.roll(y_true, 1)[1:]
    naive_mae  = float(np.mean(np.abs(y_true[1:] - naive_pred)))
    skill_score = 1 - (mae / naive_mae) if naive_mae > 0 else 0

    return {
        "model":       model_name,
        "n_samples":   len(y_true),
        "mae":         round(mae,  4),
        "rmse":        round(rmse, 4),
        "mape":        round(mape, 4),
        "bias":        round(bias, 4),
        "skill_score": round(skill_score, 4),  # > 0 means better than naive
    }


def compare_models(results: list[dict]) -> pd.DataFrame:
    """
    Compare multiple model results in a formatted table.

    Args:
        results: list of dicts from evaluate_forecast()

    Returns:
        DataFrame sorted by MAPE (best first)
    """
    df = pd.DataFrame(results).sort_values("mape")
    df["rank"] = range(1, len(df) + 1)

    logger.info("\nModel Comparison:")
    logger.info(df[["rank", "model", "mae", "rmse", "mape", "skill_score"]].to_string(index=False))
    return df


def generate_evaluation_report(
    product_id: int,
    y_true: np.ndarray,
    y_pred_xgb: np.ndarray,
    y_pred_sarima: Optional[np.ndarray] = None,
    dates: Optional[list] = None,
) -> dict:
    """
    Full evaluation report for a single product.
    Suitable for saving to DB or displaying in dashboard.
    """
    report = {
        "product_id": product_id,
        "n_test_days": len(y_true),
        "xgboost": evaluate_forecast(y_true, y_pred_xgb, "xgboost"),
    }

    if y_pred_sarima is not None:
        report["sarima"] = evaluate_forecast(y_true, y_pred_sarima, "sarima")
        # Pick winner
        report["best_model"] = (
            "xgboost" if report["xgboost"]["mape"] <= report["sarima"]["mape"]
            else "sarima"
        )
    else:
        report["best_model"] = "xgboost"

    # Grade the forecast quality
    mape = report["xgboost"]["mape"]
    if mape < 10:
        report["quality_grade"] = "Excellent (< 10% MAPE)"
    elif mape < 20:
        report["quality_grade"] = "Good (10–20% MAPE)"
    elif mape < 30:
        report["quality_grade"] = "Acceptable (20–30% MAPE)"
    else:
        report["quality_grade"] = "Needs improvement (> 30% MAPE)"

    return report


def print_summary_table(training_results_csv: str = "models/training_results.csv"):
    """Print a nicely formatted summary of all training results."""
    df = pd.read_csv(training_results_csv)
    success = df[df["xgb_status"] == "success"]

    print("\n" + "="*60)
    print("PHASE 2 TRAINING SUMMARY")
    print("="*60)
    print(f"Total products:     {len(df)}")
    print(f"Successfully trained: {len(success)}")
    print(f"Failed:              {len(df) - len(success)}")
    print(f"\nXGBoost Performance:")
    print(f"  Avg MAPE:  {success['xgb_mape'].mean():.2f}%")
    print(f"  Avg MAE:   {success['xgb_mae'].mean():.2f} units")
    print(f"  Avg RMSE:  {success['xgb_rmse'].mean():.2f} units")
    print(f"\nTop 5 Best Forecasted Products:")
    top5 = success.nsmallest(5, "xgb_mape")[["product_id", "product_name", "xgb_mape"]]
    print(top5.to_string(index=False))
    print(f"\nBottom 5 (Hardest to Forecast):")
    bot5 = success.nlargest(5, "xgb_mape")[["product_id", "product_name", "xgb_mape"]]
    print(bot5.to_string(index=False))
    print("="*60)


if __name__ == "__main__":
    print_summary_table()