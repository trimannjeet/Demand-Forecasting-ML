
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ColumnMetadata(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_percentage: float
    unique_count: int
    sample_values: list[str]


class DatasetProfileResponse(BaseModel):
    rows: int
    columns_count: int
    duplicate_rows: int
    memory_usage_bytes: int
    columns: list[ColumnMetadata]
    suggestions: dict[str, Any]


class ForecastRequestOptions(BaseModel):
    date_column: str
    target_column: str
    group_columns: list[str] = Field(default_factory=list)
    frequency: str = "auto"
    one_calendar_year: bool = True
    horizon: int | None = Field(default=None, ge=1)


class ForecastSeriesResponse(BaseModel):
    group: dict[str, Any]
    best_model: str
    frequency: str
    horizon: int
    history: list[dict[str, Any]]
    evaluation: list[dict[str, Any]]
    forecast: list[dict[str, Any]]


class ForecastResponse(BaseModel):
    filename: str
    date_column: str
    target_column: str
    group_columns: list[str]
    frequency: str
    rows_dropped: int
    series_count: int
    results: list[ForecastSeriesResponse]
