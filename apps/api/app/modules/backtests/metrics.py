from math import sqrt
from statistics import fmean, pstdev

from app.modules.backtests.types import FoldResult, MetricSet


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


def aggregate_metrics(folds: list[FoldResult]) -> dict[str, float | None]:
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


def calculate_decomposition_metrics(
    points: list[dict[str, str | float | None]],
) -> dict[str, float] | None:
    complete = [
        point
        for point in points
        if all(
            point.get(name) is not None
            for name in (
                "actual_orders",
                "predicted_orders",
                "actual_aov",
                "predicted_aov",
            )
        )
    ]
    if not complete:
        return None
    orders = calculate_metrics(
        [float(point["actual_orders"]) for point in complete],
        [float(point["predicted_orders"]) for point in complete],
    )
    aov = calculate_metrics(
        [float(point["actual_aov"]) for point in complete],
        [float(point["predicted_aov"]) for point in complete],
    )
    return {
        "orders_mae": orders.mae,
        "orders_wape": orders.wape or 0.0,
        "aov_mae": aov.mae,
        "aov_wape": aov.wape or 0.0,
    }
