
import numpy as np
import pandas as pd
import pytest

from backend.services.forecasting import (
    calculate_metrics,
    compare_models,
    forecast_series,
    _validate_series,
)


def make_daily_series(periods=120):
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    x = np.arange(periods, dtype=float)
    values = 100 + 0.5 * x + 10 * np.sin(2 * np.pi * x / 7)

    return pd.Series(values, index=dates)


def test_calculate_metrics():
    actual = np.array([100.0, 200.0, 300.0])
    predicted = np.array([110.0, 190.0, 310.0])

    metrics = calculate_metrics(actual, predicted)

    assert np.isclose(metrics["mae"], 10.0)
    assert np.isclose(metrics["rmse"], 10.0)
    assert "smape_percent" in metrics
    assert "wape_percent" in metrics
    assert np.isclose(metrics["wape_percent"], 5.0)


def test_compare_models_returns_results():
    result = compare_models(make_daily_series(), "daily")

    assert not result.empty
    assert "model" in result.columns
    assert "mae" in result.columns
    assert "rmse" in result.columns
    assert "status" in result.columns


def test_compare_models_reports_backtesting_folds():
    result = compare_models(make_daily_series(), "daily")

    evaluated = result[result["status"] == "evaluated"]

    assert not evaluated.empty
    assert (evaluated["folds"] >= 1).all()


def test_forecast_series_returns_requested_horizon():
    series = make_daily_series()

    result = forecast_series(
        series,
        frequency="daily",
        last_date=series.index[-1],
        horizon=14,
        one_calendar_year=False,
    )

    forecast = result["forecast"]

    assert len(forecast) == 14
    assert result["horizon"] == 14
    assert {"date", "prediction"}.issubset(forecast.columns)

    predictions = forecast["prediction"].to_numpy()

    assert np.isfinite(predictions).all()
    assert (predictions >= 0).all()


def test_forecast_dates_are_in_the_future():
    series = make_daily_series()

    result = forecast_series(
        series,
        frequency="daily",
        last_date=series.index[-1],
        horizon=14,
        one_calendar_year=False,
    )

    forecast_dates = pd.to_datetime(result["forecast"]["date"])

    assert len(forecast_dates) == 14
    assert (forecast_dates > series.index[-1]).all()
    assert forecast_dates.is_monotonic_increasing


def test_constant_sales_series():
    series = pd.Series(
        np.full(60, 250.0),
        index=pd.date_range("2025-01-01", periods=60, freq="D"),
    )

    result = forecast_series(
        series,
        frequency="daily",
        last_date=series.index[-1],
        horizon=7,
        one_calendar_year=False,
    )

    predictions = result["forecast"]["prediction"].to_numpy()

    assert len(predictions) == 7
    assert np.isfinite(predictions).all()
    assert (predictions >= 0).all()


def test_zero_sales_series():
    series = pd.Series(
        np.zeros(60),
        index=pd.date_range("2025-01-01", periods=60, freq="D"),
    )

    result = forecast_series(
        series,
        frequency="daily",
        last_date=series.index[-1],
        horizon=7,
        one_calendar_year=False,
    )

    predictions = result["forecast"]["prediction"].to_numpy()

    assert len(predictions) == 7
    assert np.isfinite(predictions).all()
    assert (predictions >= 0).all()


@pytest.mark.parametrize(
    "values",
    [
        [1.0, 2.0],
        [1.0, np.nan, 3.0],
        [1.0, np.inf, 3.0],
        [1.0, -np.inf, 3.0],
    ],
)
def test_validate_series_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        _validate_series(pd.Series(values))


def test_compare_models_rejects_invalid_frequency():
    with pytest.raises(ValueError, match="Frequency"):
        compare_models(make_daily_series(), "yearly")


def test_forecast_series_rejects_invalid_frequency():
    series = make_daily_series()

    with pytest.raises(ValueError, match="Frequency"):
        forecast_series(
            series,
            frequency="yearly",
            last_date=series.index[-1],
            horizon=7,
            one_calendar_year=False,
        )
