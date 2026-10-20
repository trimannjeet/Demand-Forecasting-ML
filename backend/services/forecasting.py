
from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore", category=UserWarning)

FREQUENCY_MAP = {
    "daily": "D",
    "weekly": "W-SUN",
    "monthly": "MS",
}

SEASONAL_PERIODS = {
    "daily": 7,
    "weekly": 52,
    "monthly": 12,
}


def _validate_series(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float)

    if values.isna().any() or not np.isfinite(values.to_numpy()).all():
        raise ValueError("Series contains missing or non-finite values.")

    if len(values) < 3:
        raise ValueError("At least 3 observations are required.")

    return values.reset_index(drop=True)


def calculate_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    if len(actual) != len(predicted) or len(actual) == 0:
        raise ValueError("Actual and predicted values must have equal, nonzero lengths.")

    errors = actual - predicted
    mae = float(mean_absolute_error(actual, predicted))
    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))

    denominator = np.abs(actual) + np.abs(predicted)
    smape_values = np.divide(
        200 * np.abs(errors),
        denominator,
        out=np.zeros_like(errors),
        where=denominator != 0,
    )
    smape = float(np.mean(smape_values))

    wape_denominator = float(np.sum(np.abs(actual)))
    wape = (
        float(np.sum(np.abs(errors)) / wape_denominator * 100)
        if wape_denominator > 0
        else float("nan")
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "smape_percent": smape,
        "wape_percent": wape,
    }


def _seasonal_naive_forecast(
    train: np.ndarray,
    horizon: int,
    seasonal_period: int,
) -> np.ndarray:
    if len(train) >= seasonal_period:
        pattern = train[-seasonal_period:]
    else:
        pattern = train

    repeats = int(np.ceil(horizon / len(pattern)))
    return np.tile(pattern, repeats)[:horizon].astype(float)


def _fit_predict(
    model_name: str,
    train: np.ndarray,
    horizon: int,
    seasonal_period: int,
) -> np.ndarray:
    if model_name == "Seasonal Naive":
        return _seasonal_naive_forecast(
            train, horizon, seasonal_period
        )

    if model_name == "Exponential Smoothing":
        if len(train) >= seasonal_period * 2:
            model = ExponentialSmoothing(
                train,
                trend="add",
                seasonal="add",
                seasonal_periods=seasonal_period,
                initialization_method="estimated",
            )
        else:
            model = ExponentialSmoothing(
                train,
                trend="add" if len(train) >= 6 else None,
                seasonal=None,
                initialization_method="estimated",
            )

        fitted = model.fit(optimized=True)
        return np.asarray(fitted.forecast(horizon), dtype=float)

    if model_name == "AutoReg":
        lag_count = min(seasonal_period, max(1, len(train) // 3))
        lag_count = min(lag_count, len(train) - 1)

        if lag_count < 1:
            raise ValueError("Insufficient observations for AutoReg.")

        model = AutoReg(
            train,
            lags=lag_count,
            trend="ct",
            old_names=False,
        )
        fitted = model.fit()
        return np.asarray(fitted.predict(
            start=len(train),
            end=len(train) + horizon - 1,
            dynamic=False,
        ), dtype=float)

    raise ValueError(f"Unknown model: {model_name}")


def _holdout_size(length: int, seasonal_period: int) -> int:
    desired = max(1, seasonal_period)
    return min(desired, max(1, length // 5), length - 2)



def compare_models(
    series: pd.Series,
    frequency: str,
) -> pd.DataFrame:
    """Compare models using expanding-window rolling-origin backtesting."""
    if frequency not in SEASONAL_PERIODS:
        raise ValueError("Frequency must be daily, weekly, or monthly.")

    values = _validate_series(series).to_numpy()
    seasonal_period = SEASONAL_PERIODS[frequency]

    if len(values) < 10:
        raise ValueError(
            "At least 10 observations are recommended for model comparison."
        )

    holdout = _holdout_size(len(values), seasonal_period)

    fold_count = min(
        3,
        max(1, (len(values) - 10) // holdout),
    )

    while fold_count > 1 and len(values) - fold_count * holdout < 8:
        fold_count -= 1

    candidates = [
        "Seasonal Naive",
        "Exponential Smoothing",
        "AutoReg",
    ]

    results = []

    for name in candidates:
        fold_metrics = []
        errors = []

        for fold in range(fold_count):
            train_end = len(values) - (fold_count - fold) * holdout
            test_end = min(train_end + holdout, len(values))

            train = values[:train_end]
            actual = values[train_end:test_end]

            if len(actual) == 0 or len(train) < 3:
                errors.append("Insufficient observations for a validation fold.")
                continue

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    predicted = _fit_predict(
                        name,
                        train,
                        len(actual),
                        seasonal_period,
                    )

                if (
                    len(predicted) != len(actual)
                    or not np.isfinite(predicted).all()
                ):
                    raise ValueError(
                        "Model returned invalid predictions."
                    )

                fold_metrics.append(
                    calculate_metrics(actual, predicted)
                )

            except Exception as exc:
                errors.append(f"Fold {fold + 1}: {exc}")

        if fold_metrics and not errors:
            metric_names = [
                "mae",
                "rmse",
                "smape_percent",
                "wape_percent",
            ]

            aggregated = {
                metric: float(
                    np.mean([fold[metric] for fold in fold_metrics])
                )
                for metric in metric_names
            }

            results.append({
                "model": name,
                **aggregated,
                "status": "evaluated",
                "folds": len(fold_metrics),
                "error": None,
            })
        else:
            results.append({
                "model": name,
                "mae": float("nan"),
                "rmse": float("nan"),
                "smape_percent": float("nan"),
                "wape_percent": float("nan"),
                "status": "failed",
                "folds": len(fold_metrics),
                "error": "; ".join(errors) if errors else (
                    "No successful validation folds."
                ),
            })

    return pd.DataFrame(results).sort_values(
        ["mae", "rmse"],
        na_position="last",
    ).reset_index(drop=True)



def forecast_series(
    series: pd.Series,
    frequency: str,
    last_date: str | pd.Timestamp,
    horizon: int | None = None,
    one_calendar_year: bool = True,
) -> dict[str, Any]:
    """Compare models, fit the selected model on all data, and forecast."""
    if frequency not in FREQUENCY_MAP:
        raise ValueError("Frequency must be daily, weekly, or monthly.")

    values = _validate_series(series).to_numpy()
    last_date = pd.Timestamp(last_date)

    if one_calendar_year:
        if frequency == "daily":
            future_dates = pd.date_range(
                last_date + pd.Timedelta(days=1),
                last_date + pd.DateOffset(years=1),
                freq="D",
            )
        elif frequency == "weekly":
            first = last_date + pd.Timedelta(days=7)
            end = last_date + pd.DateOffset(years=1)
            future_dates = pd.date_range(
                first, end, freq="W-SUN"
            )
        else:
            next_month = last_date.to_period("M").to_timestamp() + pd.offsets.MonthBegin(1)
            end_month = last_date.to_period("M").to_timestamp() + pd.DateOffset(years=1)
            future_dates = pd.date_range(
                next_month, end_month, freq="MS"
            )

        horizon = len(future_dates)
    else:
        if horizon is None or horizon < 1:
            raise ValueError("Provide a positive forecast horizon.")

        future_dates = pd.date_range(
            start=last_date,
            periods=horizon + 1,
            freq=FREQUENCY_MAP[frequency],
        )[1:]

    if horizon is None or horizon < 1:
        raise ValueError("Could not create a valid forecast horizon.")

    evaluation = compare_models(pd.Series(values), frequency)
    eligible = evaluation[evaluation["status"] == "evaluated"]

    if eligible.empty:
        raise RuntimeError(
            "All candidate models failed. Check your data length and values."
        )

    best_model = str(eligible.iloc[0]["model"])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        predictions = _fit_predict(
            best_model,
            values,
            horizon,
            SEASONAL_PERIODS[frequency],
        )

    if not np.isfinite(predictions).all():
        raise RuntimeError("The selected model produced non-finite forecasts.")

    predictions = np.maximum(predictions, 0.0)

    forecast_df = pd.DataFrame({
        "date": future_dates,
        "prediction": np.round(predictions, 2),
    })

    return {
        "best_model": best_model,
        "frequency": frequency,
        "horizon": int(horizon),
        "evaluation": evaluation,
        "forecast": forecast_df,
    }
