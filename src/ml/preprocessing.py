"""
Data Preprocessing Pipeline — Phase 1

Transforms raw sales data into ML-ready feature sets:
  - Missing value imputation
  - Outlier detection and handling (IQR method)
  - Time-series feature engineering:
      * Calendar features (day of week, month, quarter, etc.)
      * Lag features (7, 14, 30 days)
      * Rolling statistics (mean, std, min, max)
      * Trend indicators
  - Train/test splitting (time-aware, no shuffling!)
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Tunable settings for the preprocessing pipeline."""
    lag_days: list[int] = None          # default: [7, 14, 21, 30]
    rolling_windows: list[int] = None   # default: [7, 14, 30]
    outlier_iqr_multiplier: float = 2.5 # how aggressive outlier removal is
    test_split_days: int = 60           # hold out last 60 days for evaluation
    min_history_days: int = 60          # minimum days needed to compute all lags

    def __post_init__(self):
        if self.lag_days is None:
            self.lag_days = [7, 14, 21, 30]
        if self.rolling_windows is None:
            self.rolling_windows = [7, 14, 30]


class DataPreprocessor:
    """
    Stateless preprocessing pipeline.
    Call .process() on a raw sales DataFrame to get ML-ready features.
    """

    def __init__(self, config: PreprocessingConfig = None):
        self.config = config or PreprocessingConfig()

    # ── Public API ─────────────────────────────────────────────────────────────

    def process(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Full pipeline: raw → clean → features → validated.

        Args:
            df_raw: DataFrame with columns [product_id, date, quantity_sold,
                    revenue, is_holiday, promotion_active]

        Returns:
            Feature-rich DataFrame ready for model training.
        """
        logger.info(f"Starting preprocessing: {len(df_raw)} rows")

        df = df_raw.copy()
        df = self._validate_input(df)
        df = self._fill_missing_dates(df)
        df = self._handle_missing_values(df)
        df = self._remove_outliers(df)
        df = self._add_calendar_features(df)
        df = self._add_lag_features(df)
        df = self._add_rolling_features(df)
        df = self._add_trend_features(df)
        df = self._drop_warmup_rows(df)

        logger.info(f"Preprocessing complete: {len(df)} rows, {len(df.columns)} features")
        return df

    def train_test_split(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Time-aware split — NEVER shuffle time-series data!
        Returns (train_df, test_df) where test is the most recent N days.
        """
        cutoff = df["date"].max() - timedelta(days=self.config.test_split_days)
        train = df[df["date"] <= cutoff].copy()
        test = df[df["date"] > cutoff].copy()
        logger.info(f"Train: {len(train)} rows ({train['date'].min()} → {train['date'].max()})")
        logger.info(f"Test:  {len(test)} rows  ({test['date'].min()} → {test['date'].max()})")
        return train, test

    def get_feature_columns(self) -> list[str]:
        """Returns the list of feature column names used by the ML model."""
        features = ["day_of_week", "month", "quarter", "day_of_year",
                    "week_of_year", "is_weekend", "is_month_start",
                    "is_month_end", "is_holiday", "promotion_active"]
        for lag in self.config.lag_days:
            features.append(f"lag_{lag}d")
        for window in self.config.rolling_windows:
            features += [f"rolling_mean_{window}d", f"rolling_std_{window}d",
                         f"rolling_min_{window}d", f"rolling_max_{window}d"]
        features += ["demand_trend_7d", "demand_trend_30d", "cv_30d"]
        return features

    # ── Private Steps ──────────────────────────────────────────────────────────

    def _validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        required = ["product_id", "date", "quantity_sold"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["quantity_sold"] = pd.to_numeric(df["quantity_sold"], errors="coerce")
        df = df.sort_values(["product_id", "date"]).reset_index(drop=True)
        return df

    def _fill_missing_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure every product has a row for every date in the range.
        Missing dates = zero sales (product existed but didn't sell).
        """
        full_date_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
        full_date_range = [d.date() for d in full_date_range]

        all_products = df["product_id"].unique()
        complete_index = pd.MultiIndex.from_product(
            [all_products, full_date_range], names=["product_id", "date"]
        )
        df = (
            df.set_index(["product_id", "date"])
              .reindex(complete_index)
              .reset_index()
        )
        # Fill zeros for days with no sales
        df["quantity_sold"] = df["quantity_sold"].fillna(0).astype(int)
        df["revenue"] = df["revenue"].fillna(0.0)
        df["is_holiday"] = df["is_holiday"].fillna(False).astype(bool)
        df["promotion_active"] = df["promotion_active"].fillna(False).astype(bool)
        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Forward-fill then zero-fill any remaining nulls."""
        df["quantity_sold"] = (
            df.groupby("product_id")["quantity_sold"]
              .transform(lambda x: x.fillna(method="ffill").fillna(0))
        )
        return df

    def _remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        IQR-based outlier capping per product.
        Instead of dropping outliers (which breaks time continuity),
        we cap them at the IQR fence — preserving the signal without the spike.
        """
        def cap_outliers(series: pd.Series) -> pd.Series:
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - self.config.outlier_iqr_multiplier * iqr
            upper = q3 + self.config.outlier_iqr_multiplier * iqr
            return series.clip(lower=max(0, lower), upper=upper)

        df["quantity_sold"] = (
            df.groupby("product_id")["quantity_sold"]
              .transform(cap_outliers)
        )
        return df

    def _add_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract time-based features that capture seasonality and cyclicality."""
        dt = pd.to_datetime(df["date"])
        df["day_of_week"] = dt.dt.dayofweek          # 0=Monday, 6=Sunday
        df["month"] = dt.dt.month
        df["quarter"] = dt.dt.quarter
        df["day_of_year"] = dt.dt.dayofyear
        df["week_of_year"] = dt.dt.isocalendar().week.astype(int)
        df["year"] = dt.dt.year
        df["is_weekend"] = (dt.dt.dayofweek >= 5).astype(int)
        df["is_month_start"] = dt.dt.is_month_start.astype(int)
        df["is_month_end"] = dt.dt.is_month_end.astype(int)
        df["is_holiday"] = df["is_holiday"].astype(int)
        df["promotion_active"] = df["promotion_active"].astype(int)
        return df

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Lag features: demand N days ago.
        These are the most powerful features for demand forecasting —
        they let the model see recent history directly.
        """
        for lag in self.config.lag_days:
            df[f"lag_{lag}d"] = (
                df.groupby("product_id")["quantity_sold"]
                  .transform(lambda x: x.shift(lag))
            )
        return df

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Rolling window statistics to capture recent demand trends and volatility.
        All windows use closed='left' to avoid look-ahead leakage.
        """
        for window in self.config.rolling_windows:
            grp = df.groupby("product_id")["quantity_sold"]
            df[f"rolling_mean_{window}d"] = grp.transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).mean()
            )
            df[f"rolling_std_{window}d"] = grp.transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).std().fillna(0)
            )
            df[f"rolling_min_{window}d"] = grp.transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).min()
            )
            df[f"rolling_max_{window}d"] = grp.transform(
                lambda x: x.shift(1).rolling(window, min_periods=1).max()
            )
        return df

    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Trend = recent avg demand vs older avg demand.
        Positive = demand growing, Negative = demand declining.
        CV (coefficient of variation) = demand unpredictability.
        """
        grp = df.groupby("product_id")["quantity_sold"]

        # 7-day trend: recent 7d avg vs previous 7d avg
        df["demand_trend_7d"] = (
            grp.transform(lambda x: x.shift(1).rolling(7, min_periods=1).mean()) -
            grp.transform(lambda x: x.shift(8).rolling(7, min_periods=1).mean())
        )

        # 30-day trend
        df["demand_trend_30d"] = (
            grp.transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean()) -
            grp.transform(lambda x: x.shift(31).rolling(30, min_periods=1).mean())
        )

        # Coefficient of variation (std / mean) over 30d → demand volatility
        rolling_mean = grp.transform(
            lambda x: x.shift(1).rolling(30, min_periods=1).mean()
        )
        rolling_std = grp.transform(
            lambda x: x.shift(1).rolling(30, min_periods=1).std().fillna(0)
        )
        df["cv_30d"] = (rolling_std / rolling_mean.replace(0, np.nan)).fillna(0)

        return df

    def _drop_warmup_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Drop the first N rows per product — they have NaN lags/rolling stats
        from the warmup period. We can't use rows without full feature history.
        """
        min_date = pd.to_datetime(df["date"].min()) + timedelta(
            days=self.config.min_history_days
        )
        df = df[pd.to_datetime(df["date"]) >= min_date].reset_index(drop=True)
        return df


# ─── Convenience Function ─────────────────────────────────────────────────────

def load_and_preprocess(product_id: int = None, db=None) -> pd.DataFrame:
    """
    Load sales from DB and run full preprocessing pipeline.

    Args:
        product_id: if None, processes all products.
        db: SQLAlchemy session (uses get_db_context() if None).

    Returns:
        Preprocessed, ML-ready DataFrame.
    """
    from src.api.models import Sale
    from src.api.database import get_db_context

    ctx = db if db else get_db_context()

    with (ctx if db is None else _null_context(db)) as session:
        query = session.query(Sale)
        if product_id:
            query = query.filter(Sale.product_id == product_id)
        records = query.all()

    df_raw = pd.DataFrame([{
        "product_id": r.product_id,
        "date": r.date,
        "quantity_sold": r.quantity_sold,
        "revenue": r.revenue,
        "is_holiday": r.is_holiday,
        "promotion_active": r.promotion_active,
    } for r in records])

    preprocessor = DataPreprocessor()
    return preprocessor.process(df_raw)


from contextlib import contextmanager

@contextmanager
def _null_context(obj):
    """Passthrough context manager — used when db session is already open."""
    yield obj
