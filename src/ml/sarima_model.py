"""
SARIMA Baseline Forecasting Model — Phase 2

Uses statsmodels SARIMAX with auto parameter selection via pmdarima.
SARIMA is the statistical benchmark — if XGBoost can't beat it,
something is wrong with the feature engineering.
"""

import logging
import warnings
import numpy as np
import pandas as pd
import joblib
import os
from datetime import timedelta

warnings.filterwarnings("ignore")  # suppress statsmodels convergence warnings
logger = logging.getLogger(__name__)

MODELS_DIR = "models"
os.makedirs(MODELS_DIR, exist_ok=True)


class SARIMAForecaster:
    """
    SARIMA demand forecaster — statistical baseline model.

    Uses pmdarima's auto_arima to automatically find the best
    (p,d,q)(P,D,Q,m) parameters via AIC minimization.
    """

    def __init__(self, product_id: int):
        self.product_id = product_id
        self.model = None
        self.order = None        # (p, d, q)
        self.seasonal_order = None  # (P, D, Q, m)
        self.train_metrics_: dict = {}

    def train(self, df: pd.DataFrame) -> dict:
        """
        Fit SARIMA model on product's historical demand.

        Args:
            df: Preprocessed DataFrame (output of DataPreprocessor)

        Returns:
            dict with MAE, RMSE, MAPE on held-out test period
        """
        try:
            import pmdarima as pm
        except ImportError:
            raise ImportError("Run: pip install pmdarima")

        product_df = (
            df[df["product_id"] == self.product_id]
            .sort_values("date")
            .reset_index(drop=True)
        )

        if len(product_df) < 60:
            raise ValueError(f"Need at least 60 days of data for SARIMA.")

        demand = product_df["quantity_sold"].values

        # Train/test split — last 30 days as test
        train_demand = demand[:-30]
        test_demand  = demand[-30:]

        logger.info(f"Fitting SARIMA for product {self.product_id} "
                    f"({len(train_demand)} train days)...")

        # auto_arima searches for best parameters automatically
        # m=7 = weekly seasonality
        auto_model = pm.auto_arima(
            train_demand,
            m=7,                    # weekly seasonality period
            seasonal=True,
            stepwise=True,          # faster than exhaustive search
            suppress_warnings=True,
            error_action="ignore",
            max_p=3, max_q=3,
            max_P=2, max_Q=2,
            information_criterion="aic",
            n_jobs=-1,
        )

        self.model = auto_model
        self.order = auto_model.order
        self.seasonal_order = auto_model.seasonal_order

        logger.info(f"  Best SARIMA order: {self.order} x {self.seasonal_order}")

        # Evaluate on test set
        test_preds = auto_model.predict(n_periods=30)
        test_preds = np.clip(test_preds, 0, None)

        metrics = self._compute_metrics(test_demand, test_preds)
        self.train_metrics_ = metrics

        logger.info(f"  Test MAE: {metrics['mae']:.2f}, "
                    f"RMSE: {metrics['rmse']:.2f}, "
                    f"MAPE: {metrics['mape']:.2f}%")

        # Save model
        self._save_model()
        return metrics

    def predict_next_n_days(self, n_days: int = 30) -> pd.DataFrame:
        """
        Forecast next N days demand.

        Returns:
            DataFrame with [date, predicted_demand, lower_bound, upper_bound]
        """
        if self.model is None:
            raise ValueError("Model not trained. Call .train() first.")

        preds, conf_int = self.model.predict(
            n_periods=n_days,
            return_conf_int=True,
            alpha=0.05,  # 95% confidence interval
        )
        preds = np.clip(preds, 0, None)

        # Generate future dates
        last_date = pd.Timestamp.today()
        dates = [(last_date + timedelta(days=i+1)).date() for i in range(n_days)]

        return pd.DataFrame({
            "date": dates,
            "predicted_demand": np.round(preds, 2),
            "lower_bound": np.clip(np.round(conf_int[:, 0], 2), 0, None),
            "upper_bound": np.round(conf_int[:, 1], 2),
        })

    def _compute_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        mae  = mean_absolute_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mask = y_true != 0
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
        return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4)}

    def _save_model(self):
        path = os.path.join(MODELS_DIR, f"sarima_product_{self.product_id}.joblib")
        joblib.dump(self.model, path)
        logger.info(f"SARIMA model saved to {path}")

    @classmethod
    def load(cls, product_id: int) -> "SARIMAForecaster":
        path = os.path.join(MODELS_DIR, f"sarima_product_{product_id}.joblib")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No saved model at {path}")
        instance = cls(product_id=product_id)
        instance.model = joblib.load(path)
        return instance