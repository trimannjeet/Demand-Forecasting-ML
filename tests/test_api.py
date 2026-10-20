
from io import BytesIO

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def make_csv():
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    values = 100 + np.arange(120, dtype=float) * 0.5

    df = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "Sales": values,
    })

    return df.to_csv(index=False).encode("utf-8")


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200


def test_render_frontend_origin_is_allowed_by_cors():
    response = client.options(
        "/profile",
        headers={
            "Origin": "https://demand-forecasting-ml-1.onrender.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://demand-forecasting-ml-1.onrender.com"
    )


def test_profile_endpoint():
    response = client.post(
        "/profile",
        files={
            "file": (
                "sales.csv",
                BytesIO(make_csv()),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["filename"] == "sales.csv"
    assert result["rows"] == 120
    assert result["columns_count"] == 2
    assert "columns" in result
    assert "suggestions" in result




def test_forecast_endpoint():
    response = client.post(
        "/forecast",
        files={
            "file": (
                "sales.csv",
                BytesIO(make_csv()),
                "text/csv",
            )
        },
        data={
            "date_column": "Date",
            "target_column": "Sales",
            "group_columns": "",
            "frequency": "daily",
            "one_calendar_year": "false",
            "horizon": "14",
            "missing_period": "zero",
        },
    )

    assert response.status_code == 200, response.text

    result = response.json()
    assert isinstance(result, dict)
    series = result["results"][0]
    assert len(series["history"]) == 120
    assert series["history"][0]["value"] == 100.0
    assert len(series["forecast"]) == 14
