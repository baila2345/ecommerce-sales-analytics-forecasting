from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
from math import log1p
from statistics import fmean, pstdev

from app.modules.backtests.datasets import RevenueAsOfIndex
from app.modules.backtests.features.direct_revenue import (
    DIRECT_CALENDAR_FEATURE_NAMES,
    calendar_feature_values,
    safe_ratio,
)
from app.modules.backtests.types import BacktestDataset


MIN_ACTIVE_COMPONENT_DAYS = 21
MAX_ORDERS_TARGET_RATIO = 10.0
MAX_AOV_TARGET_RATIO = 5.0
_HISTORY_FEATURE_SUFFIXES = (
    "level_log1p_28",
    "lag_1_ratio_28",
    "lag_7_ratio_28",
    "lag_14_ratio_28",
    "lag_28_ratio_28",
    "rolling_mean_7_ratio_28",
    "rolling_mean_14_ratio_28",
    "rolling_cv_7",
    "rolling_cv_14",
    "rolling_cv_28",
    "growth_7_vs_previous_7",
    "growth_14_vs_previous_14",
    "growth_28_vs_previous_28",
)
ORDERS_FEATURE_NAMES = (
    *DIRECT_CALENDAR_FEATURE_NAMES,
    *(f"orders_{name}" for name in _HISTORY_FEATURE_SUFFIXES),
)
AOV_FEATURE_NAMES = (
    *DIRECT_CALENDAR_FEATURE_NAMES,
    *(f"aov_{name}" for name in _HISTORY_FEATURE_SUFFIXES),
)
DECOMPOSITION_FEATURE_SCHEMA_HASH = sha256(
    json.dumps(
        {
            "orders_features": ORDERS_FEATURE_NAMES,
            "aov_features": AOV_FEATURE_NAMES,
            "orders_target": "orders_divided_by_origin_mean_28",
            "aov_target": "aov_divided_by_origin_mean_28",
            "min_active_component_days": MIN_ACTIVE_COMPONENT_DAYS,
            "max_orders_target_ratio": MAX_ORDERS_TARGET_RATIO,
            "max_aov_target_ratio": MAX_AOV_TARGET_RATIO,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class ComponentContext:
    features: list[float]
    scale: float
    active_days: int


@dataclass(frozen=True)
class DecompositionTrainingData:
    orders_rows: list[list[float]]
    orders_targets: list[float]
    aov_rows: list[list[float]]
    aov_targets: list[float]


@dataclass(frozen=True)
class DecompositionForecastData:
    orders_rows: list[list[float]]
    orders_scale: float
    aov_rows: list[list[float]]
    aov_scale: float


def _mean_present(values: list[float | None]) -> float:
    present = [value for value in values if value is not None]
    return fmean(present) if present else 0.0


def _component_context(values: list[float | None]) -> ComponentContext:
    means = {
        window: _mean_present(values[:window]) for window in (7, 14, 28)
    }
    scale = means[28]
    normalized_values = [scale if value is None else value for value in values]
    features = [
        log1p(max(0.0, scale)),
        *[
            safe_ratio(normalized_values[offset], scale)
            for offset in (0, 6, 13, 27)
        ],
        safe_ratio(means[7], scale),
        safe_ratio(means[14], scale),
    ]
    for window in (7, 14, 28):
        window_values = [
            value for value in values[:window] if value is not None
        ]
        deviation = pstdev(window_values) if len(window_values) > 1 else 0.0
        features.append(safe_ratio(deviation, means[window]))
    for window in (7, 14, 28):
        previous_mean = _mean_present(values[window : window * 2])
        features.append(safe_ratio(means[window] - previous_mean, previous_mean))
    return ComponentContext(
        features=features,
        scale=scale,
        active_days=sum(value is not None and value > 0 for value in values[:28]),
    )


def _contexts_at_origin(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    origin_date: date,
) -> tuple[ComponentContext, ComponentContext]:
    cutoff = origin_date - timedelta(days=dataset.maturity_days)
    dates = [cutoff - timedelta(days=offset) for offset in range(56)]
    orders = [float(index.order_count(value, origin_date)) for value in dates]
    aov = [index.aov(value, origin_date) for value in dates]
    return _component_context(orders), _component_context(aov)


def _rows(
    context: ComponentContext,
    *,
    origin_date: date,
    forecast_dates: list[date],
) -> list[list[float]]:
    return [
        [
            *calendar_feature_values(
                origin_date=origin_date,
                target_date=target_date,
            ),
            *context.features,
        ]
        for target_date in forecast_dates
    ]


def build_decomposition_forecast_data(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    origin_date: date,
    forecast_dates: list[date],
) -> DecompositionForecastData:
    orders_context, aov_context = _contexts_at_origin(
        dataset, index, origin_date
    )
    if min(orders_context.active_days, aov_context.active_days) < MIN_ACTIVE_COMPONENT_DAYS:
        raise ValueError(
            "M3 requires at least "
            f"{MIN_ACTIVE_COMPONENT_DAYS} active days in each component scale window"
        )
    return DecompositionForecastData(
        orders_rows=_rows(
            orders_context,
            origin_date=origin_date,
            forecast_dates=forecast_dates,
        ),
        orders_scale=orders_context.scale,
        aov_rows=_rows(
            aov_context,
            origin_date=origin_date,
            forecast_dates=forecast_dates,
        ),
        aov_scale=aov_context.scale,
    )


def build_decomposition_training_data(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    fit_origin: date,
    horizon_days: int,
) -> DecompositionTrainingData:
    first_date = dataset.actuals[0].date
    origin_date = first_date + timedelta(days=dataset.maturity_days + 55)
    known_label_cutoff = fit_origin - timedelta(days=dataset.maturity_days)
    last_origin = known_label_cutoff - timedelta(days=horizon_days)
    orders_rows: list[list[float]] = []
    orders_targets: list[float] = []
    aov_rows: list[list[float]] = []
    aov_targets: list[float] = []
    while origin_date <= last_origin:
        orders_context, aov_context = _contexts_at_origin(
            dataset, index, origin_date
        )
        if min(orders_context.active_days, aov_context.active_days) < MIN_ACTIVE_COMPONENT_DAYS:
            origin_date += timedelta(days=1)
            continue
        forecast_dates = [
            origin_date + timedelta(days=lead_day)
            for lead_day in range(1, horizon_days + 1)
        ]
        origin_orders_rows = _rows(
            orders_context,
            origin_date=origin_date,
            forecast_dates=forecast_dates,
        )
        origin_aov_rows = _rows(
            aov_context,
            origin_date=origin_date,
            forecast_dates=forecast_dates,
        )
        for target_date, orders_row, aov_row in zip(
            forecast_dates,
            origin_orders_rows,
            origin_aov_rows,
            strict=True,
        ):
            target_orders = index.order_count(target_date, fit_origin)
            orders_rows.append(orders_row)
            orders_targets.append(
                min(
                    MAX_ORDERS_TARGET_RATIO,
                    max(0.0, safe_ratio(target_orders, orders_context.scale)),
                )
            )
            target_aov = index.aov(target_date, fit_origin)
            if target_aov is not None:
                aov_rows.append(aov_row)
                aov_targets.append(
                    min(
                        MAX_AOV_TARGET_RATIO,
                        max(0.0, safe_ratio(target_aov, aov_context.scale)),
                    )
                )
        origin_date += timedelta(days=1)
    if not orders_rows or not aov_rows:
        raise ValueError("No leakage-safe training samples are available for M3")
    return DecompositionTrainingData(
        orders_rows=orders_rows,
        orders_targets=orders_targets,
        aov_rows=aov_rows,
        aov_targets=aov_targets,
    )
