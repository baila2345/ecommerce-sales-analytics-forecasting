from dataclasses import dataclass
from datetime import date, timedelta
from math import sqrt
from statistics import fmean, pstdev


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


def seasonal_naive_forecast(
    train: list[SeriesPoint],
    forecast_dates: list[date],
    season_length: int = 7,
) -> list[float]:
    history = {point.date: point.value for point in train}
    predictions: list[float] = []
    for forecast_date in forecast_dates:
        source_date = forecast_date - timedelta(days=season_length)
        if source_date not in history:
            raise ValueError("Training history does not cover the seasonal lag")
        prediction = history[source_date]
        predictions.append(prediction)
        history[forecast_date] = prediction
    return predictions


def calculate_metrics(actual: list[float], predicted: list[float]) -> MetricSet:
    errors = [
        actual_value - predicted_value
        for actual_value, predicted_value in zip(actual, predicted, strict=True)
    ]
    absolute_errors = [abs(error) for error in errors]
    actual_sum = sum(actual)
    return MetricSet(
        mae=fmean(absolute_errors),
        rmse=sqrt(fmean(error * error for error in errors)),
        wape=(sum(absolute_errors) / actual_sum * 100 if actual_sum else None),
        actual_sum=actual_sum,
        prediction_sum=sum(predicted),
    )


def run_seasonal_naive_backtest(
    series: list[SeriesPoint],
    *,
    horizon_days: int,
    holdout_days: int,
    min_train_days: int,
    step_days: int,
    season_length: int = 7,
) -> BacktestResult:
    _validate_contiguous_series(series)
    minimum_days = min_train_days + holdout_days + (horizon_days * 3)
    if len(series) < minimum_days:
        raise ValueError(
            f"At least {minimum_days} mature days are required; got {len(series)}"
        )

    development = series[:-holdout_days]
    holdout = series[-holdout_days:]
    folds: list[FoldResult] = []
    test_start_index = min_train_days
    while test_start_index + horizon_days <= len(development):
        train = development[:test_start_index]
        test = development[test_start_index : test_start_index + horizon_days]
        predictions = seasonal_naive_forecast(
            train,
            [point.date for point in test],
            season_length,
        )
        metrics = calculate_metrics(
            [point.value for point in test], predictions
        )
        folds.append(
            FoldResult(
                fold_no=len(folds) + 1,
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
        metrics=_aggregate_metrics(folds),
        holdout_from=holdout[0].date,
        holdout_to=holdout[-1].date,
    )


def _aggregate_metrics(folds: list[FoldResult]) -> dict[str, float | None]:
    maes = [fold.metrics.mae for fold in folds]
    rmses = [fold.metrics.rmse for fold in folds]
    wapes = [
        fold.metrics.wape for fold in folds if fold.metrics.wape is not None
    ]
    return {
        "mae_mean": fmean(maes),
        "mae_std": pstdev(maes),
        "rmse_mean": fmean(rmses),
        "rmse_std": pstdev(rmses),
        "wape_mean": fmean(wapes) if wapes else None,
        "wape_std": pstdev(wapes) if wapes else None,
    }


def _validate_contiguous_series(series: list[SeriesPoint]) -> None:
    if not series:
        raise ValueError("The mature daily sales series is empty")
    for previous, current in zip(series, series[1:]):
        if current.date != previous.date + timedelta(days=1):
            raise ValueError("The mature daily sales series must be contiguous")
