
import numpy as np
import pandas as pd
import pytest

from backend.services.data_processor import (
    profile_dataset,
    suggest_columns,
    detect_frequency,
    prepare_series,
    _parse_dates,
)


@pytest.fixture
def sample_data():
    dates = pd.date_range("2025-01-01", periods=90, freq="D")
    return pd.DataFrame({
        "Date": dates,
        "Sales": np.arange(100, 190, dtype=float),
        "Store": ["Store A"] * 90,
    })


def test_profile_dataset(sample_data):
    result = profile_dataset(sample_data)

    assert result["rows"] == 90
    assert result["columns_count"] == 3
    assert "columns" in result
    assert len(result["columns"]) == 3



def test_suggest_columns(sample_data):
    result = suggest_columns(sample_data)

    date_columns = [
        item["column"] for item in result["date_candidates"]
    ]
    target_columns = [
        item["column"] for item in result["target_candidates"]
    ]

    assert "Date" in date_columns
    assert "Sales" in target_columns
    assert result["suggested_date_column"] == "Date"
    assert result["suggested_target_column"] == "Sales"


def test_detect_daily_frequency(sample_data):
    result = detect_frequency(sample_data["Date"])

    assert result["frequency"] == "daily"


def test_parse_iso_and_day_first_dates_without_swapping_month_and_day():
    dates = pd.Series(["2024-01-02", "2024-02-03", "05-02-2010"])

    parsed = _parse_dates(dates)

    assert parsed.tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-02-03"),
        pd.Timestamp("2010-02-05"),
    ]


def test_prepare_daily_series(sample_data):
    result = prepare_series(
        sample_data,
        date_column="Date",
        target_column="Sales",
        frequency="daily",
    )

    assert result["frequency"] == "daily"
    assert result["date_column"] == "Date"
    assert result["target_column"] == "Sales"
    assert len(result["data"]) == 90


def test_prepare_series_fills_missing_dates_with_zero(sample_data):
    sample_data = sample_data.drop(index=10).reset_index(drop=True)

    result = prepare_series(
        sample_data,
        date_column="Date",
        target_column="Sales",
        frequency="daily",
        missing_period_value=0.0,
    )

    assert len(result["data"]) == 90
    assert (result["data"]["Sales"] == 0).any()


def test_prepare_series_rejects_invalid_columns(sample_data):
    with pytest.raises((ValueError, KeyError)):
        prepare_series(
            sample_data,
            date_column="WrongDate",
            target_column="Sales",
            frequency="daily",
        )
