from datetime import timedelta

from app.modules.backtests.metrics import aggregate_metrics, calculate_metrics
from app.modules.backtests.models.base import ForecastModel
from app.modules.backtests.types import (
    BacktestResult,
    FoldExecutionError,
    FoldResult,
    SeriesPoint,
)


def run_rolling_backtest(
    series: list[SeriesPoint],
    *,
    model: ForecastModel,
    horizon_days: int,
    holdout_days: int,
    min_train_days: int,
    step_days: int,
) -> BacktestResult:
    development, holdout = split_development_holdout(
        series,
        horizon_days=horizon_days,
        holdout_days=holdout_days,
        min_train_days=min_train_days,
    )
    folds: list[FoldResult] = []
    test_start_index = min_train_days
    while test_start_index + horizon_days <= len(development):
        fold_no = len(folds) + 1
        train = development[:test_start_index]
        test = development[test_start_index : test_start_index + horizon_days]
        try:
            predictions = model.forecast(
                train,
                [point.date for point in test],
            )
        except Exception as exc:
            raise FoldExecutionError(model.code, fold_no, str(exc)) from exc
        if len(predictions) != len(test):
            raise FoldExecutionError(
                model.code,
                fold_no,
                f"Expected {len(test)} predictions; got {len(predictions)}",
            )
        metrics = calculate_metrics(
            [point.value for point in test], predictions
        )
        folds.append(
            FoldResult(
                fold_no=fold_no,
                origin_date=train[-1].date,
                train_from=train[0].date,
                train_to=train[-1].date,
                test_from=test[0].date,
                test_to=test[-1].date,
                metrics=metrics,
                predictions=[
                    {
                        "date": point.date.isoformat(),
                        "actual": point.value,
                        "predicted": prediction,
                    }
                    for point, prediction in zip(test, predictions, strict=True)
                ],
            )
        )
        test_start_index += step_days

    if len(folds) < 3:
        raise ValueError(f"At least 3 folds are required; got {len(folds)}")
    return BacktestResult(
        folds=folds,
        metrics=aggregate_metrics(folds),
        holdout_from=holdout[0].date,
        holdout_to=holdout[-1].date,
    )


def validate_contiguous_series(series: list[SeriesPoint]) -> None:
    if not series:
        raise ValueError("The mature daily sales series is empty")
    for previous, current in zip(series, series[1:]):
        if current.date != previous.date + timedelta(days=1):
            raise ValueError("The mature daily sales series must be contiguous")


def split_development_holdout(
    series: list[SeriesPoint],
    *,
    horizon_days: int,
    holdout_days: int,
    min_train_days: int,
) -> tuple[list[SeriesPoint], list[SeriesPoint]]:
    validate_contiguous_series(series)
    minimum_days = min_train_days + holdout_days + (horizon_days * 3)
    if len(series) < minimum_days:
        raise ValueError(
            f"At least {minimum_days} mature days are required; got {len(series)}"
        )
    return series[:-holdout_days], series[-holdout_days:]
