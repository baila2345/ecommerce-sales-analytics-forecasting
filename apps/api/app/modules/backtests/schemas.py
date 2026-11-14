from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    model_code: Literal["M0", "M1"] = "M0"
    dataset_fingerprint: str | None = Field(
        default=None, min_length=64, max_length=64
    )
    horizon_days: Literal[7, 30] = 30
    holdout_days: int = Field(default=90, ge=30, le=180)
    min_train_days: int = Field(default=365, ge=90, le=730)
    step_days: int = Field(default=30, ge=7, le=90)
    season_length: int = Field(default=7, ge=2, le=30)
    sarima_order: tuple[int, int, int] = Field(default=(1, 1, 1))
    sarima_seasonal_order: tuple[int, int, int, int] = Field(
        default=(1, 0, 1, 7)
    )
    sarima_maxiter: int = Field(default=100, ge=10, le=500)


class FoldMetricsResponse(BaseModel):
    mae: float
    rmse: float
    wape: float | None
    actual_sum: float
    prediction_sum: float


class PredictionPointResponse(BaseModel):
    date: date
    actual: float
    predicted: float


class BacktestFoldResponse(BaseModel):
    fold_no: int
    origin_date: date
    train_from: date
    train_to: date
    test_from: date
    test_to: date
    metrics: FoldMetricsResponse
    predictions: list[PredictionPointResponse]


class AggregateMetricsResponse(BaseModel):
    mae_mean: float
    mae_std: float
    rmse_mean: float
    rmse_std: float
    wape_mean: float | None
    wape_std: float | None


class BacktestRunResponse(BaseModel):
    id: int
    model_code: str
    status: str
    dataset_fingerprint: str
    snapshot_id: int
    horizon_days: int
    holdout_from: date
    holdout_to: date
    holdout_evaluated: bool = False
    fold_count: int
    metrics: AggregateMetricsResponse | None
    folds: list[BacktestFoldResponse]
    job_id: str | None
    error: dict | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
