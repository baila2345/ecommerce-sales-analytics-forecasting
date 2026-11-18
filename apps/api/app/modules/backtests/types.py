from dataclasses import dataclass
from datetime import date
from functools import cached_property


@dataclass(frozen=True)
class SeriesPoint:
    date: date
    value: float


@dataclass(frozen=True)
class RevenueEvent:
    purchase_date: date
    delivered_date: date
    value: float


@dataclass(frozen=True)
class BacktestDataset:
    actuals: list[SeriesPoint]
    revenue_events: list[RevenueEvent]
    maturity_days: int

    @cached_property
    def actual_by_date(self) -> dict[date, float]:
        return {point.date: point.value for point in self.actuals}


@dataclass(frozen=True)
class ForecastOutput:
    predictions: list[float]
    components: list[dict[str, float]] | None = None


@dataclass(frozen=True)
class MetricSet:
    mae: float
    rmse: float
    wape: float | None
    actual_sum: float
    prediction_sum: float


@dataclass(frozen=True)
class FoldResult:
    fold_no: int
    origin_date: date
    train_from: date
    train_to: date
    test_from: date
    test_to: date
    metrics: MetricSet
    predictions: list[dict[str, str | float | None]]


@dataclass(frozen=True)
class BacktestResult:
    folds: list[FoldResult]
    metrics: dict[str, float | None]
    holdout_from: date
    holdout_to: date


class FoldExecutionError(RuntimeError):
    def __init__(self, model_code: str, fold_no: int, message: str) -> None:
        self.model_code = model_code
        self.fold_no = fold_no
        super().__init__(message)
