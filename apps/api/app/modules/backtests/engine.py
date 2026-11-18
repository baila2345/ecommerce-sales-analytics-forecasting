from datetime import date, timedelta

from app.modules.backtests.metrics import aggregate_metrics, calculate_metrics
from app.modules.backtests.datasets import (
    RevenueAsOfIndex,
    dataset_from_series,
    known_series_at,
)
from app.modules.backtests.models.base import (
    ForecastModel,
    SeriesModelAdapter,
    TemporalForecastModel,
)
from app.modules.backtests.types import (
    BacktestDataset,
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
    return run_temporal_rolling_backtest(
        dataset_from_series(series),
        model=SeriesModelAdapter(model),
        horizon_days=horizon_days,
        holdout_days=holdout_days,
        min_train_days=min_train_days,
        step_days=step_days,
    )


def run_temporal_rolling_backtest(
    dataset: BacktestDataset,
    *,
    model: TemporalForecastModel,
    horizon_days: int,
    holdout_days: int,
    min_train_days: int,
    step_days: int,
) -> BacktestResult:
    development, holdout = split_development_holdout(
        dataset.actuals,
        horizon_days=horizon_days,
        holdout_days=holdout_days,
        min_train_days=min_train_days,
        maturity_days=dataset.maturity_days,
    )
    index = RevenueAsOfIndex(dataset.revenue_events)
    folds: list[FoldResult] = []
    test_start_index = min_train_days + dataset.maturity_days
    while test_start_index + horizon_days <= len(development):
        fold_no = len(folds) + 1
        test = development[test_start_index : test_start_index + horizon_days]
        origin_date = test[0].date - timedelta(days=1)
        train = known_series_at(dataset, index, origin_date)
        try:
            forecast = model.forecast(
                dataset,
                index,
                origin_date,
                [point.date for point in test],
            )
        except Exception as exc:
            raise FoldExecutionError(model.code, fold_no, str(exc)) from exc
        predictions = forecast.predictions
        if len(predictions) != len(test):
            raise FoldExecutionError(
                model.code,
                fold_no,
                f"Expected {len(test)} predictions; got {len(predictions)}",
            )
        if forecast.components is not None and len(forecast.components) != len(test):
            raise FoldExecutionError(
                model.code,
                fold_no,
                "Forecast components must align with predictions",
            )
        metrics = calculate_metrics(
            [point.value for point in test], predictions
        )
        prediction_points: list[dict[str, str | float | None]] = []
        for index_value, (point, prediction) in enumerate(
            zip(test, predictions, strict=True)
        ):
            prediction_point: dict[str, str | float | None] = {
                "date": point.date.isoformat(),
                "actual": point.value,
                "predicted": prediction,
            }
            if forecast.components is not None:
                actual_orders = index.order_count(point.date, date.max)
                actual_aov = index.aov(point.date, date.max)
                prediction_point.update(forecast.components[index_value])
                prediction_point.update(
                    {
                        "actual_orders": float(actual_orders),
                        "actual_aov": actual_aov,
                    }
                )
            prediction_points.append(prediction_point)
        folds.append(
            FoldResult(
                fold_no=fold_no,
                origin_date=origin_date,
                train_from=train[0].date,
                train_to=train[-1].date,
                test_from=test[0].date,
                test_to=test[-1].date,
                metrics=metrics,
                predictions=prediction_points,
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
    maturity_days: int = 0,
) -> tuple[list[SeriesPoint], list[SeriesPoint]]:
    validate_contiguous_series(series)
    minimum_days = (
        min_train_days
        + maturity_days
        + holdout_days
        + (horizon_days * 3)
    )
    if len(series) < minimum_days:
        raise ValueError(
            f"At least {minimum_days} mature days are required; got {len(series)}"
        )
    return series[:-holdout_days], series[-holdout_days:]
