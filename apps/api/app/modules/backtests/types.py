from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeriesPoint:
    date: date
    value: float


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
    predictions: list[dict[str, str | float]]


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
