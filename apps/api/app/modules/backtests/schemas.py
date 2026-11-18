from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class BacktestRequest(BaseModel):
    model_code: Literal["M0", "M1", "M2", "M3"] = "M0"
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
    m2_n_estimators: int = Field(default=200, ge=50, le=1000)
    m2_learning_rate: float = Field(default=0.05, gt=0, le=0.3)
    m2_num_leaves: int = Field(default=15, ge=4, le=128)
    m2_max_depth: int = Field(default=5, ge=2, le=12)
    m2_min_child_samples: int = Field(default=20, ge=5, le=200)
    m2_seed: int = Field(default=42, ge=0, le=2_147_483_647)
    m3_n_estimators: int = Field(default=200, ge=50, le=1000)
    m3_learning_rate: float = Field(default=0.05, gt=0, le=0.3)
    m3_num_leaves: int = Field(default=15, ge=4, le=128)
    m3_max_depth: int = Field(default=5, ge=2, le=12)
    m3_min_child_samples: int = Field(default=20, ge=5, le=200)
    m3_seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def validate_sarima_parameters(self) -> "BacktestRequest":
        p, d, q = self.sarima_order
        seasonal_p, seasonal_d, seasonal_q, period = self.sarima_seasonal_order
        if p > 5 or q > 5 or d > 2 or min(p, d, q) < 0:
            raise ValueError("SARIMA order requires p/q in 0..5 and d in 0..2")
        if (
            seasonal_p > 3
            or seasonal_q > 3
            or seasonal_d > 2
            or min(seasonal_p, seasonal_d, seasonal_q) < 0
            or not 2 <= period <= 30
        ):
            raise ValueError(
                "SARIMA seasonal order requires P/Q in 0..3, D in 0..2, "
                "and period in 2..30"
            )
        return self


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
    predicted_orders: float | None = None
    predicted_aov: float | None = None
    actual_orders: float | None = None
    actual_aov: float | None = None


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


class DecompositionMetricsResponse(BaseModel):
    orders_mae: float
    orders_wape: float
    aov_mae: float
    aov_wape: float


class BacktestRunResponse(BaseModel):
    id: int
    model_code: str
    status: str
    dataset_fingerprint: str
    snapshot_id: int
    horizon_days: int
    holdout_days: int
    min_train_days: int
    step_days: int
    experiment_key: str | None
    model_version: str | None
    feature_schema_hash: str | None
    holdout_from: date
    holdout_to: date
    holdout_evaluated: bool = False
    fold_count: int
    metrics: AggregateMetricsResponse | None
    component_metrics: DecompositionMetricsResponse | None
    folds: list[BacktestFoldResponse]
    job_id: str | None
    error: dict | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
