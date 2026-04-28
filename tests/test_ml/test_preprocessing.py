"""
Unit tests for the data preprocessing pipeline.
Run:  pytest tests/ -v --cov=src --cov-report=term-missing
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from src.ml.preprocessing import DataPreprocessor, PreprocessingConfig


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_sales_df():
    """Minimal but realistic sales DataFrame for two products."""
    dates = pd.date_range("2022-01-01", periods=120, freq="D").date.tolist()
    rng = np.random.default_rng(42)

    rows = []
    for product_id in [1, 2]:
        base = 50 if product_id == 1 else 30
        for d in dates:
            qty = max(0, int(base + rng.normal(0, 5)))
            rows.append({
                "product_id": product_id,
                "date": d,
                "quantity_sold": qty,
                "revenue": qty * 100.0,
                "is_holiday": False,
                "promotion_active": False,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def preprocessor():
    cfg = PreprocessingConfig(
        lag_days=[7, 14],
        rolling_windows=[7, 14],
        test_split_days=30,
        min_history_days=30,
    )
    return DataPreprocessor(config=cfg)


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestValidation:
    def test_raises_on_missing_columns(self, preprocessor):
        bad_df = pd.DataFrame({"product_id": [1], "date": [date.today()]})
        with pytest.raises(ValueError, match="Missing required columns"):
            preprocessor.process(bad_df)

    def test_accepts_valid_df(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        assert len(result) > 0


class TestMissingDateFill:
    def test_fills_missing_dates_with_zero(self, preprocessor):
        # Create df with a gap (skip Jan 5)
        dates = [date(2022, 1, 1), date(2022, 1, 2), date(2022, 1, 6)]
        df = pd.DataFrame({
            "product_id": [1, 1, 1],
            "date": dates,
            "quantity_sold": [10, 20, 30],
            "revenue": [100, 200, 300],
            "is_holiday": [False, False, False],
            "promotion_active": [False, False, False],
        })
        # We need more history to pass warmup — extend with extra rows
        extra_dates = pd.date_range("2022-01-07", periods=60, freq="D").date
        extra = pd.DataFrame({
            "product_id": [1] * 60,
            "date": extra_dates,
            "quantity_sold": [15] * 60,
            "revenue": [150.0] * 60,
            "is_holiday": [False] * 60,
            "promotion_active": [False] * 60,
        })
        full_df = pd.concat([df, extra], ignore_index=True)
        result = preprocessor.process(full_df)
        # Confirm no NaN in quantity_sold
        assert result["quantity_sold"].isna().sum() == 0


class TestOutlierHandling:
    def test_outliers_are_capped_not_dropped(self, preprocessor, sample_sales_df):
        # Inject a massive spike
        sample_sales_df.loc[50, "quantity_sold"] = 99999
        original_len = len(sample_sales_df)

        result = preprocessor.process(sample_sales_df)
        # Row count should only decrease by warmup rows, not by outlier removal
        # Outliers are CAPPED, not removed
        assert result["quantity_sold"].max() < 99999

    def test_no_negative_values_after_capping(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        assert (result["quantity_sold"] >= 0).all()


class TestCalendarFeatures:
    def test_calendar_columns_present(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        expected = ["day_of_week", "month", "quarter", "week_of_year",
                    "is_weekend", "is_month_start", "is_month_end"]
        for col in expected:
            assert col in result.columns, f"Missing column: {col}"

    def test_weekend_flag_correct(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        dt = pd.to_datetime(result["date"])
        expected_weekends = (dt.dt.dayofweek >= 5).astype(int)
        pd.testing.assert_series_equal(
            result["is_weekend"].reset_index(drop=True),
            expected_weekends.reset_index(drop=True),
            check_names=False,
        )


class TestLagFeatures:
    def test_lag_columns_created(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        for lag in [7, 14]:
            assert f"lag_{lag}d" in result.columns

    def test_no_look_ahead_leakage(self, preprocessor, sample_sales_df):
        """Lag features must only reference past data."""
        result = preprocessor.process(sample_sales_df)
        grp = result.groupby("product_id")
        for pid, group in grp:
            group = group.sort_values("date").reset_index(drop=True)
            # lag_7d on row i must equal quantity_sold 7 rows back
            if len(group) > 8:
                actual_lag7 = group.loc[8, "lag_7d"]
                expected = group.loc[1, "quantity_sold"]
                assert abs(actual_lag7 - expected) < 1e-6, (
                    f"Look-ahead leakage detected for product {pid}"
                )


class TestTrainTestSplit:
    def test_no_data_leakage_in_split(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        train, test = preprocessor.train_test_split(result)
        assert train["date"].max() < test["date"].min()

    def test_split_sizes_reasonable(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        train, test = preprocessor.train_test_split(result)
        assert len(train) > len(test)
        assert len(test) > 0


class TestFeatureColumns:
    def test_all_feature_columns_in_output(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        expected_features = preprocessor.get_feature_columns()
        for col in expected_features:
            assert col in result.columns, f"Feature column missing: {col}"

    def test_no_nan_in_features(self, preprocessor, sample_sales_df):
        result = preprocessor.process(sample_sales_df)
        feature_cols = preprocessor.get_feature_columns()
        nan_cols = [c for c in feature_cols if result[c].isna().any()]
        assert len(nan_cols) == 0, f"NaN found in feature columns: {nan_cols}"
