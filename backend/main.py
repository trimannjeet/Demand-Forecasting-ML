
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.data_processor import (
    load_dataset,
    profile_dataset,
    prepare_series,
    suggest_columns,
)
from backend.services.forecasting import forecast_series


MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_GROUPS = 45
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

app = FastAPI(
    title="Demand Forecasting API",
    description=(
        "Upload business data, inspect columns, compare forecasting "
        "models, and generate future demand predictions."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def json_safe(value: Any) -> Any:
    """Convert NumPy/Pandas values into JSON-safe Python values."""
    if value is None:
        return None

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()

    if isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if pd.isna(value):
        return None

    return value


async def read_upload(upload: UploadFile) -> tuple[pd.DataFrame, str]:
    """Validate an upload and load it using a temporary file."""
    filename = Path(upload.filename or "dataset.csv").name
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Upload a CSV, XLSX, or XLS file.",
        )

    content = await upload.read(MAX_UPLOAD_BYTES + 1)

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 25 MB upload limit.",
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        df = load_dataset(temp_path)
        return df, filename

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read dataset: {exc}",
        ) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Demand Forecasting API",
        "version": "1.0.0",
    }


@app.get("/")
def root():
    return {
        "service": "Demand Forecasting API",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/profile")
async def profile(file: UploadFile = File(...)):
    df, filename = await read_upload(file)

    try:
        profile_info = profile_dataset(df)
        suggestions = suggest_columns(df)

        return json_safe({
            "filename": filename,
            **profile_info,
            "suggestions": suggestions,
        })
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset profiling failed: {exc}",
        ) from exc


@app.post("/forecast")
async def create_forecast(
    file: UploadFile = File(...),
    date_column: str = Form(...),
    target_column: str = Form(...),
    group_columns: str = Form(""),
    frequency: str = Form("auto"),
    one_calendar_year: bool = Form(True),
    horizon: int | None = Form(None),
    missing_period: str = Form("zero"),
):
    df, filename = await read_upload(file)

    selected_groups = [
        item.strip()
        for item in group_columns.split(",")
        if item.strip()
    ]

    if len(selected_groups) != len(set(selected_groups)):
        raise HTTPException(
            status_code=422,
            detail="Duplicate grouping columns were selected.",
        )

    if missing_period not in {"zero", "keep"}:
        raise HTTPException(
            status_code=422,
            detail="missing_period must be 'zero' or 'keep'.",
        )

    if not one_calendar_year and (horizon is None or horizon < 1):
        raise HTTPException(
            status_code=422,
            detail="Provide a positive horizon when not forecasting one calendar year.",
        )

    try:
        prepared = prepare_series(
            df=df,
            date_column=date_column,
            target_column=target_column,
            group_columns=selected_groups,
            frequency=frequency,
            missing_period_value=(
                0.0 if missing_period == "zero" else None
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not prepare time series: {exc}",
        ) from exc

    data = prepared["data"]

    if missing_period == "keep" and data[target_column].isna().any():
        raise HTTPException(
            status_code=422,
            detail=(
                "Missing periods remain in the prepared series. "
                "Choose missing_period='zero' or provide a dataset "
                "with complete periods before forecasting."
            ),
        )

    if selected_groups:
        grouped = list(
            data.groupby(
                selected_groups,
                dropna=False,
                sort=False,
            )
        )
        if len(grouped) > MAX_GROUPS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"This request contains {len(grouped)} groups. "
                    f"Please filter to at most {MAX_GROUPS} groups per request."
                ),
            )
    else:
        grouped = [(None, data)]

    results = []

    for group_key, part in grouped:
        part = part.sort_values("date")

        group_values = (
            group_key if isinstance(group_key, tuple)
            else (group_key,)
        ) if selected_groups else ()

        group_info = {
            column: value
            for column, value in zip(selected_groups, group_values)
        }

        try:
            output = forecast_series(
                series=part[target_column],
                frequency=prepared["frequency"],
                last_date=part["date"].max(),
                horizon=horizon,
                one_calendar_year=one_calendar_year,
            )

            results.append({
                "group": group_info,
                "best_model": output["best_model"],
                "frequency": output["frequency"],
                "horizon": output["horizon"],
                "history": [
                    {
                        "date": row["date"],
                        "value": row[target_column],
                    }
                    for row in part[["date", target_column]].to_dict(
                        orient="records"
                    )
                ],
                "evaluation": output["evaluation"].to_dict(
                    orient="records"
                ),
                "forecast": output["forecast"].to_dict(
                    orient="records"
                ),
            })

        except Exception as exc:
            results.append({
                "group": group_info,
                "error": str(exc),
            })

    successful = [
        item for item in results if "error" not in item
    ]

    if not successful:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Forecasting failed for every selected series.",
                "results": json_safe(results),
            },
        )

    return json_safe({
        "filename": filename,
        "date_column": date_column,
        "target_column": target_column,
        "group_columns": selected_groups,
        "frequency": prepared["frequency"],
        "rows_dropped": prepared["rows_dropped"],
        "series_count": len(results),
        "results": results,
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
