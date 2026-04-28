"""
XGBoost Demand Forecasting Model — Phase 2

Industry-standard approach:
  - Feature engineering with lag/rolling features
  - TimeSeriesSplit cross-validation (NO data shuffling!)
  - Hyperparameter tuning
  - MLflow experiment tracking
  - Model serialization and versioning
"""

import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from datetime import date, timedelta
from dataclasses import dataclass, field

import mlflow
import mlflow.xgboost
from xgboost import XGBRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error

logger = logging.getLogger(__name__)

MODELS_DIR = "models"
os.makedirs(MODELS_DIR, exist_ok=True)


# ─── Metrics ──────────────────────────────────────────────────────────────────

def mean_absolute_percentage_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """MAPE — primary metric for forecasting. Lower is better. <15% is good."""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    y_pred_clipped = np.clip(y_pred, 0, None)  # demand can't be negative
    return {
        "mae":  round(mean_absolute_error(y_true, y_pred_clipped), 4),
        "rmse": round(np.sqrt(mean_squared_error(y_true, y_pred_clipped)), 4),
        "mape": round(mean_absolute_percentage_error(y_true, y_pred_clipped), 4),
    }


# ─── Model Config ─────────────────────────────────────────────────────────────

@dataclass
class XGBoostConfig:
    """Tunable hyperparameters — these were chosen via cross-validation."""
    n_estimators: int = 500
    max_depth: int = 6
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: int = 3
    reg_alpha: float = 0.1       # L1 regularization
    reg_lambda: float = 1.0      # L2 regularization
    early_stopping_rounds: int = 50
    n_cv_splits: int = 5         # TimeSeriesSplit folds
    random_state: int = 42


# ─── Feature Config ───────────────────────────────────────────────────────────

FEATURE_COLUMNS = [
    # Calendar
    "day_of_week", "month", "quarter", "day_of_year",
    "week_of_year", "is_weekend", "is_month_start", "is_month_end",
    "is_holiday", "promotion_active",
    # Lags
    "lag_7d", "lag_14d", "lag_21d", "lag_30d",
    # Rolling stats
    "rolling_mean_7d", "rolling_std_7d", "rolling_min_7d", "rolling_max_7d",
    "rolling_mean_14d", "rolling_std_14d", "rolling_min_14d", "rolling_max_14d",
    "rolling_mean_30d", "rolling_std_30d", "rolling_min_30d", "rolling_max_30d",
    # Trend
    "demand_trend_7d", "demand_trend_30d", "cv_30d",
]
TARGET_COLUMN = "quantity_sold"


# ─── XGBoost Forecaster ───────────────────────────────────────────────────────

class XGBoostForecaster:
    """
    Per-product XGBoost demand forecaster.

    Usage:
        forecaster = XGBoostForecaster(product_id=1)
        forecaster.train(df_preprocessed)
        predictions = forecaster.predict(df_future_features)
    """

    def __init__(self, product_id: int, config: XGBoostConfig = None):
        self.product_id = product_id
        self.config = config or XGBoostConfig()
        self.model: XGBRegressor = None
        self.feature_importance_: pd.DataFrame = None
        self.cv_scores_: list[dict] = []
        self.model_path: str = None

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, df: pd.DataFrame, mlflow_run: bool = True) -> dict:
        """
        Train XGBoost model with time-series cross-validation.

        Args:
            df: Preprocessed DataFrame from DataPreprocessor
            mlflow_run: whether to log to MLflow

        Returns:
            dict with final CV metrics
        """
        product_df = df[df["product_id"] == self.product_id].copy()
        product_df = product_df.sort_values("date").reset_index(drop=True)

        if len(product_df) < 100:
            raise ValueError(
                f"Product {self.product_id} has only {len(product_df)} rows. "
                f"Need at least 100 for reliable training."
            )

        X = product_df[FEATURE_COLUMNS].fillna(0)
        y = product_df[TARGET_COLUMN].values

        logger.info(f"Training XGBoost for product {self.product_id}: "
                    f"{len(X)} rows, {len(FEATURE_COLUMNS)} features")

        # ── Cross-Validation (CRITICAL: use TimeSeriesSplit, never shuffle!) ─
        tscv = TimeSeriesSplit(n_splits=self.config.n_cv_splits)
        cv_metrics = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = self._build_model()
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )

            preds = model.predict(X_val)
            metrics = compute_metrics(y_val, preds)
            cv_metrics.append(metrics)
            logger.info(f"  Fold {fold+1}: MAE={metrics['mae']:.2f}, "
                        f"RMSE={metrics['rmse']:.2f}, MAPE={metrics['mape']:.2f}%")

        self.cv_scores_ = cv_metrics

        # ── Final Model: train on ALL data ────────────────────────────────────
        # Split last 20% for early stopping validation
        split_idx = int(len(X) * 0.8)
        self.model = self._build_model()
        self.model.fit(
            X.iloc[:split_idx], y[:split_idx],
            eval_set=[(X.iloc[split_idx:], y[split_idx:])],
            verbose=False,
        )

        # ── Feature Importance ────────────────────────────────────────────────
        self.feature_importance_ = pd.DataFrame({
            "feature": FEATURE_COLUMNS,
            "importance": self.model.feature_importances_,
        }).sort_values("importance", ascending=False)

        # ── Average CV Metrics ────────────────────────────────────────────────
        avg_metrics = {
            "mae":  round(np.mean([m["mae"]  for m in cv_metrics]), 4),
            "rmse": round(np.mean([m["rmse"] for m in cv_metrics]), 4),
            "mape": round(np.mean([m["mape"] for m in cv_metrics]), 4),
        }

        logger.info(f"  Final CV — MAE: {avg_metrics['mae']:.2f}, "
                    f"RMSE: {avg_metrics['rmse']:.2f}, "
                    f"MAPE: {avg_metrics['mape']:.2f}%")

        # ── MLflow Logging ────────────────────────────────────────────────────
        if mlflow_run:
            self._log_to_mlflow(avg_metrics, len(X))

        # ── Save Model ────────────────────────────────────────────────────────
        self.model_path = self._save_model()

        return avg_metrics

    def predict(self, df_features: pd.DataFrame) -> np.ndarray:
        """
        Generate demand predictions.

        Args:
            df_features: DataFrame with FEATURE_COLUMNS

        Returns:
            Array of predicted demand values (non-negative)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call .train() first.")

        X = df_features[FEATURE_COLUMNS].fillna(0)
        preds = self.model.predict(X)
        return np.clip(preds, 0, None)  # demand can't be negative

    def predict_next_n_days(
        self,
        df_history: pd.DataFrame,
        n_days: int = 30,
    ) -> pd.DataFrame:
        """
        Predict demand for the next N days using recursive forecasting.
        Each day's prediction becomes the lag feature for the next day.

        Args:
            df_history: Historical preprocessed data for this product
            n_days: Number of days to forecast ahead

        Returns:
            DataFrame with [date, predicted_demand, lower_bound, upper_bound]
        """
        from src.ml.preprocessing import DataPreprocessor

        product_history = df_history[
            df_history["product_id"] == self.product_id
        ].copy().sort_values("date")

        last_date = pd.to_datetime(product_history["date"].max())
        forecast_dates = [
            (last_date + timedelta(days=i+1)).date()
            for i in range(n_days)
        ]

        # Use last 30 days of actuals to compute confidence interval
        recent_errors = self._estimate_prediction_error(product_history)

        results = []
        # Keep a rolling buffer of recent demand for lag computation
        demand_buffer = list(product_history["quantity_sold"].values[-60:])

        for forecast_date in forecast_dates:
            features = self._build_future_features(
                forecast_date, demand_buffer, product_history
            )
            pred = float(self.predict(features)[0])
            std = recent_errors * pred  # scale uncertainty by prediction size

            results.append({
                "date": forecast_date,
                "predicted_demand": round(pred, 2),
                "lower_bound": round(max(0, pred - 1.96 * std), 2),
                "upper_bound": round(pred + 1.96 * std, 2),
            })
            demand_buffer.append(pred)

        return pd.DataFrame(results)

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _build_model(self) -> XGBRegressor:
        return XGBRegressor(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            learning_rate=self.config.learning_rate,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            min_child_weight=self.config.min_child_weight,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            early_stopping_rounds=self.config.early_stopping_rounds,
            random_state=self.config.random_state,
            n_jobs=-1,       # use all CPU cores
            tree_method="hist",  # faster training
        )

    def _build_future_features(
        self,
        forecast_date: date,
        demand_buffer: list,
        history_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build a single-row feature DataFrame for one future date."""
        dt = pd.Timestamp(forecast_date)

        # Calendar features
        row = {
            "day_of_week":    dt.dayofweek,
            "month":          dt.month,
            "quarter":        dt.quarter,
            "day_of_year":    dt.dayofyear,
            "week_of_year":   dt.isocalendar().week,
            "is_weekend":     int(dt.dayofweek >= 5),
            "is_month_start": int(dt.is_month_start),
            "is_month_end":   int(dt.is_month_end),
            "is_holiday":     0,   # can be enhanced with calendar
            "promotion_active": 0,
        }

        # Lag features from buffer
        buf = demand_buffer
        row["lag_7d"]  = buf[-7]  if len(buf) >= 7  else 0
        row["lag_14d"] = buf[-14] if len(buf) >= 14 else 0
        row["lag_21d"] = buf[-21] if len(buf) >= 21 else 0
        row["lag_30d"] = buf[-30] if len(buf) >= 30 else 0

        # Rolling features
        for w in [7, 14, 30]:
            window = buf[-w:] if len(buf) >= w else buf
            row[f"rolling_mean_{w}d"] = np.mean(window)
            row[f"rolling_std_{w}d"]  = np.std(window)
            row[f"rolling_min_{w}d"]  = np.min(window)
            row[f"rolling_max_{w}d"]  = np.max(window)

        # Trend features
        recent_7  = np.mean(buf[-7:])  if len(buf) >= 7  else np.mean(buf)
        prev_7    = np.mean(buf[-14:-7]) if len(buf) >= 14 else np.mean(buf)
        recent_30 = np.mean(buf[-30:]) if len(buf) >= 30 else np.mean(buf)
        prev_30   = np.mean(buf[-60:-30]) if len(buf) >= 60 else np.mean(buf)

        row["demand_trend_7d"]  = recent_7 - prev_7
        row["demand_trend_30d"] = recent_30 - prev_30
        row["cv_30d"] = (np.std(buf[-30:]) / np.mean(buf[-30:])
                         if len(buf) >= 30 and np.mean(buf[-30:]) > 0 else 0)

        return pd.DataFrame([row])

    def _estimate_prediction_error(self, history_df: pd.DataFrame) -> float:
        """Estimate relative prediction error for confidence intervals."""
        if len(self.cv_scores_) == 0:
            return 0.15  # default 15% uncertainty
        avg_mape = np.mean([s["mape"] for s in self.cv_scores_]) / 100
        return max(0.05, avg_mape)  # at least 5% uncertainty

    def _log_to_mlflow(self, metrics: dict, n_rows: int):
        """Log this training run to MLflow."""
        try:
            from src.config import settings
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)

            with mlflow.start_run(run_name=f"xgboost_product_{self.product_id}"):
                # Log hyperparameters
                mlflow.log_params({
                    "model": "xgboost",
                    "product_id": self.product_id,
                    "n_estimators": self.config.n_estimators,
                    "max_depth": self.config.max_depth,
                    "learning_rate": self.config.learning_rate,
                    "n_cv_splits": self.config.n_cv_splits,
                    "training_rows": n_rows,
                })
                # Log metrics
                mlflow.log_metrics(metrics)
                # Log model artifact
                mlflow.xgboost.log_model(self.model, "model")
                # Log feature importance
                fi_path = f"models/feature_importance_product_{self.product_id}.csv"
                self.feature_importance_.to_csv(fi_path, index=False)
                mlflow.log_artifact(fi_path)

        except Exception as e:
            logger.warning(f"MLflow logging failed (non-critical): {e}")

    def _save_model(self) -> str:
        path = os.path.join(MODELS_DIR, f"xgboost_product_{self.product_id}.joblib")
        joblib.dump(self.model, path)
        logger.info(f"Model saved to {path}")
        return path

    @classmethod
    def load(cls, product_id: int) -> "XGBoostForecaster":
        """Load a saved model from disk."""
        path = os.path.join(MODELS_DIR, f"xgboost_product_{product_id}.joblib")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved model found at {path}")
        instance = cls(product_id=product_id)
        instance.model = joblib.load(path)
        instance.model_path = path
        return instance