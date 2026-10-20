
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
SUPPORTED_FREQUENCIES = {"daily", "weekly", "monthly"}


def load_dataset(file_path: str | Path) -> pd.DataFrame:
    """Load a supported CSV or Excel dataset."""
    path = Path(file_path)

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported file format. Upload a CSV, XLSX, or XLS file."
        )

    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    if df.empty:
        raise ValueError("The uploaded dataset is empty.")

    if len(df.columns) == 0:
        raise ValueError("The dataset contains no columns.")

    df.columns = [str(column).strip() for column in df.columns]

    if any(not column for column in df.columns):
        raise ValueError("Column names cannot be empty.")

    if df.columns.duplicated().any():
        raise ValueError("Duplicate column names were found.")

    return df


def profile_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Return dataset overview and per-column metadata."""
    if df.empty:
        raise ValueError("Cannot profile an empty dataset.")

    columns = []

    for column in df.columns:
        series = df[column]
        sample_values = (
            series.dropna()
            .astype(str)
            .drop_duplicates()
            .head(5)
            .tolist()
        )

        columns.append(
            {
                "name": str(column),
                "dtype": str(series.dtype),
                "null_count": int(series.isna().sum()),
                "null_percentage": round(
                    float(series.isna().mean() * 100), 2
                ),
                "unique_count": int(series.nunique(dropna=True)),
                "sample_values": sample_values,
            }
        )

    return {
        "rows": int(len(df)),
        "columns_count": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_usage_bytes": int(
            df.memory_usage(deep=True).sum()
        ),
        "columns": columns,
    }


def _parse_dates(series: pd.Series) -> pd.Series:
    """Parse common date formats, including day-first dates."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    values = series.astype("string").str.strip()
    iso_dates = values.str.match(
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[T\s].*)?$",
        na=False,
    )
    parsed_iso = pd.to_datetime(
        values.where(iso_dates),
        errors="coerce",
        dayfirst=False,
    )
    other_values = values.where(~iso_dates)

    try:
        parsed_other = pd.to_datetime(
            other_values,
            errors="coerce",
            format="mixed",
            dayfirst=True,
        )
    except (TypeError, ValueError):
        parsed_other = pd.to_datetime(
            other_values,
            errors="coerce",
            dayfirst=True,
        )

    return parsed_iso.combine_first(parsed_other)


def suggest_columns(
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Suggest date, target, and possible grouping columns."""
    date_candidates = []
    target_candidates = []
    identifier_candidates = []

    for column in df.columns:
        name = str(column).strip().lower()
        series = df[column]

        date_name_match = any(
            token in name
            for token in ("date", "datetime", "timestamp", "period")
        )

        parsed_dates = _parse_dates(series)
        parse_ratio = float(parsed_dates.notna().mean())

        if (
            date_name_match and parse_ratio >= 0.5
        ) or (
            parse_ratio >= 0.8
            and not pd.api.types.is_numeric_dtype(series)
        ):
            date_candidates.append(
                {
                    "column": column,
                    "parse_ratio": round(parse_ratio, 3),
                }
            )

        numeric = pd.to_numeric(series, errors="coerce")
        numeric_ratio = float(numeric.notna().mean())

        target_name_match = any(
            token in name
            for token in (
                "sales", "revenue", "quantity", "demand",
                "units", "amount", "orders", "target"
            )
        )

        if numeric_ratio >= 0.7 and numeric.notna().any():
            score = int(target_name_match) * 2
            target_candidates.append(
                {
                    "column": column,
                    "score": score,
                    "numeric_ratio": round(numeric_ratio, 3),
                }
            )

        unique_count = int(series.nunique(dropna=True))

        if (
            not pd.api.types.is_numeric_dtype(series)
            and unique_count > 1
            and unique_count < len(df)
        ):
            identifier_candidates.append(
                {
                    "column": column,
                    "unique_count": unique_count,
                }
            )

    target_candidates.sort(
        key=lambda item: (
            item["score"], item["numeric_ratio"]
        ),
        reverse=True,
    )

    return {
        "date_candidates": date_candidates,
        "target_candidates": target_candidates,
        "possible_group_columns": identifier_candidates,
        "suggested_date_column": (
            date_candidates[0]["column"]
            if date_candidates else None
        ),
        "suggested_target_column": (
            target_candidates[0]["column"]
            if target_candidates else None
        ),
    }


def detect_frequency(
    dates: pd.Series,
) -> dict[str, Any]:
    """Heuristically detect daily, weekly, or monthly observations."""
    parsed = _parse_dates(dates).dropna()
    unique_dates = pd.Series(parsed.unique()).sort_values()

    if len(unique_dates) < 3:
        return {
            "frequency": None,
            "median_gap_days": None,
            "confidence": "low",
            "message": "At least three unique dates are recommended.",
        }

    gaps = unique_dates.diff().dropna().dt.total_seconds() / 86400
    median_gap = float(gaps.median())

    if median_gap <= 2:
        frequency = "daily"
    elif median_gap <= 10:
        frequency = "weekly"
    elif median_gap <= 45:
        frequency = "monthly"
    else:
        frequency = None

    regularity = (
        float((gaps - median_gap).abs().le(
            max(1.0, median_gap * 0.25)
        ).mean())
        if median_gap > 0 else 0.0
    )

    return {
        "frequency": frequency,
        "median_gap_days": round(median_gap, 2),
        "confidence": (
            "high" if regularity >= 0.8
            else "medium" if regularity >= 0.5
            else "low"
        ),
        "regularity_score": round(regularity, 3),
        "message": (
            "Frequency is a heuristic. Confirm it against the dataset."
        ),
    }


def _normalize_dates(
    dates: pd.Series,
    frequency: str,
) -> pd.Series:
    if frequency == "daily":
        return dates.dt.normalize()

    if frequency == "weekly":
        return (
            dates.dt.to_period("W-SUN")
            .dt.end_time.dt.normalize()
        )

    if frequency == "monthly":
        return (
            dates.dt.to_period("M")
            .dt.end_time.dt.normalize()
        )

    raise ValueError(
        f"Unsupported frequency: {frequency}"
    )


def prepare_series(
    df: pd.DataFrame,
    date_column: str,
    target_column: str,
    group_columns: list[str] | None = None,
    frequency: str = "auto",
    missing_period_value: float | None = 0.0,
) -> dict[str, Any]:
    """
    Clean and aggregate data into a regular time series.

    Missing periods are filled with missing_period_value.
    Set it to None to retain missing target values instead.
    """
    group_columns = group_columns or []

    if date_column not in df.columns:
        raise ValueError(f"Date column not found: {date_column}")

    if target_column not in df.columns:
        raise ValueError(
            f"Target column not found: {target_column}"
        )

    if date_column == target_column:
        raise ValueError("Date and target columns must differ.")

    if len(set(group_columns)) != len(group_columns):
        raise ValueError("Duplicate grouping columns were selected.")

    for column in group_columns:
        if column not in df.columns:
            raise ValueError(
                f"Grouping column not found: {column}"
            )
        if column in {date_column, target_column}:
            raise ValueError(
                "Date and target columns cannot also be grouping columns."
            )

    if frequency not in {"auto", *SUPPORTED_FREQUENCIES}:
        raise ValueError(
            "Frequency must be auto, daily, weekly, or monthly."
        )

    work = df[[date_column, target_column] + group_columns].copy()

    work[date_column] = _parse_dates(work[date_column])
    work[target_column] = pd.to_numeric(
        work[target_column], errors="coerce"
    )

    rows_before = len(work)
    work = work.dropna(subset=[date_column, target_column])
    dropped_rows = rows_before - len(work)

    if work.empty:
        raise ValueError(
            "No usable rows remain after parsing dates and target values."
        )

    if not np.isfinite(work[target_column].to_numpy(dtype=float)).all():
        raise ValueError(
            "Target contains infinite values. Clean them before forecasting."
        )

    if frequency == "auto":
        detected = detect_frequency(work[date_column])
        frequency = detected["frequency"]

        if frequency is None:
            raise ValueError(
                "Could not confidently classify the frequency. "
                "Choose daily, weekly, or monthly manually."
            )
    else:
        detected = detect_frequency(work[date_column])

    work["_period"] = _normalize_dates(
        work[date_column], frequency
    )

    keys = ["_period"] + group_columns
    aggregated = (
        work.groupby(keys, dropna=False, as_index=False)[target_column]
        .sum()
        .rename(columns={"_period": "date"})
        .sort_values(["date"] + group_columns)
        .reset_index(drop=True)
    )

    completed_parts = []

    grouped = (
        aggregated.groupby(group_columns, dropna=False, sort=False)
        if group_columns
        else [(None, aggregated)]
    )

    pandas_frequency = {
        "daily": "D",
        "weekly": "W-SUN",
        "monthly": "ME",
    }[frequency]

    for group_key, part in grouped:
        part = part.sort_values("date").copy()

        full_dates = pd.date_range(
            start=part["date"].min(),
            end=part["date"].max(),
            freq=pandas_frequency,
        )

        part = (
            part.set_index("date")
            .reindex(full_dates)
            .rename_axis("date")
            .reset_index()
        )

        if group_columns:
            group_values = (
                group_key if isinstance(group_key, tuple)
                else (group_key,)
            )

            for column, value in zip(group_columns, group_values):
                part[column] = value

        if missing_period_value is not None:
            part[target_column] = part[target_column].fillna(
                missing_period_value
            )

        completed_parts.append(part)

    result = pd.concat(
        completed_parts, ignore_index=True
    ).sort_values(["date"] + group_columns).reset_index(drop=True)

    return {
        "data": result,
        "frequency": frequency,
        "date_column": date_column,
        "target_column": target_column,
        "group_columns": group_columns,
        "rows_dropped": int(dropped_rows),
        "detected_frequency": detected,
        "missing_period_value": missing_period_value,
    }
