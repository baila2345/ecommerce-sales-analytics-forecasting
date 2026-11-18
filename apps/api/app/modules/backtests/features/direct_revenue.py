from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
import json
from math import log1p
from statistics import fmean, pstdev

from app.modules.backtests.datasets import RevenueAsOfIndex
from app.modules.backtests.types import BacktestDataset


DIRECT_CALENDAR_FEATURE_NAMES = (
    "lead_day",
    "target_day_of_week",
    "target_day_of_month",
    "target_month",
    "target_quarter",
    "target_is_weekend",
    "target_is_black_friday_window",
    "target_black_friday_distance",
)
DIRECT_FEATURE_NAMES = (
    *DIRECT_CALENDAR_FEATURE_NAMES,
    "revenue_level_log1p_28",
    "revenue_lag_1_ratio_28",
    "revenue_lag_7_ratio_28",
    "revenue_lag_14_ratio_28",
    "revenue_lag_28_ratio_28",
    "revenue_rolling_mean_7_ratio_28",
    "revenue_rolling_mean_14_ratio_28",
    "revenue_rolling_cv_7",
    "revenue_rolling_cv_14",
    "revenue_rolling_cv_28",
    "revenue_growth_7_vs_previous_7",
    "revenue_growth_14_vs_previous_14",
    "revenue_growth_28_vs_previous_28",
)
MIN_ACTIVE_SCALE_DAYS = 21
MAX_TARGET_RATIO = 10.0
DIRECT_FEATURE_SCHEMA_HASH = sha256(
    json.dumps(
        {
            "feature_names": DIRECT_FEATURE_NAMES,
            "target": "revenue_divided_by_origin_mean_28",
            "min_active_scale_days": MIN_ACTIVE_SCALE_DAYS,
            "max_target_ratio": MAX_TARGET_RATIO,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class DirectFeatureContext:
    features: list[float]
    revenue_scale: float
    active_scale_days: int


def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / max(abs(denominator), 1.0)


def _mean(values: list[float], start: int, end: int) -> float:
    return fmean(values[start:end])


def _history_features(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    origin_date: date,
) -> DirectFeatureContext:
    cutoff = origin_date - timedelta(days=dataset.maturity_days)
    values = [
        index.value(cutoff - timedelta(days=offset), origin_date)
        for offset in range(56)
    ]
    means = {window: _mean(values, 0, window) for window in (7, 14, 28)}
    scale = means[28]
    features = [
        log1p(max(0.0, scale)),
        *[safe_ratio(values[offset], scale) for offset in (0, 6, 13, 27)],
        safe_ratio(means[7], scale),
        safe_ratio(means[14], scale),
    ]
    for window in (7, 14, 28):
        window_values = values[:window]
        features.append(safe_ratio(pstdev(window_values), means[window]))
    for window in (7, 14, 28):
        previous_mean = _mean(values, window, window * 2)
        features.append(safe_ratio(means[window] - previous_mean, previous_mean))
    return DirectFeatureContext(
        features=features,
        revenue_scale=scale,
        active_scale_days=sum(value > 0 for value in values[:28]),
    )


def _black_friday(target_date: date) -> date:
    november_first = date(target_date.year, 11, 1)
    first_friday_offset = (4 - november_first.weekday()) % 7
    return november_first + timedelta(days=first_friday_offset + 21)


def _black_friday_features(target_date: date) -> tuple[float, float]:
    distance = abs((target_date - _black_friday(target_date)).days)
    return float(distance <= 7), float(min(distance, 15))


def calendar_feature_values(
    *, origin_date: date, target_date: date
) -> list[float]:
    black_friday_window, black_friday_distance = _black_friday_features(
        target_date
    )
    return [
        float((target_date - origin_date).days),
        float(target_date.weekday()),
        float(target_date.day),
        float(target_date.month),
        float((target_date.month - 1) // 3 + 1),
        float(target_date.weekday() >= 5),
        black_friday_window,
        black_friday_distance,
    ]


def _row(
    context: DirectFeatureContext,
    *,
    lead_day: int,
    target_date: date,
) -> list[float]:
    return [
        *calendar_feature_values(
            origin_date=target_date - timedelta(days=lead_day),
            target_date=target_date,
        ),
        *context.features,
    ]


def build_forecast_matrix(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    origin_date: date,
    forecast_dates: list[date],
) -> list[list[float]]:
    context = _history_features(dataset, index, origin_date)
    if context.active_scale_days < MIN_ACTIVE_SCALE_DAYS:
        raise ValueError(
            "M2 requires at least "
            f"{MIN_ACTIVE_SCALE_DAYS} revenue days in its 28-day scale window"
        )
    return [
        _row(
            context,
            lead_day=(target_date - origin_date).days,
            target_date=target_date,
        )
        for target_date in forecast_dates
    ]


def revenue_scale_at_origin(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    origin_date: date,
) -> float:
    return _history_features(dataset, index, origin_date).revenue_scale


def build_training_matrix(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    fit_origin: date,
    horizon_days: int,
) -> tuple[list[list[float]], list[float]]:
    first_date = dataset.actuals[0].date
    first_origin = first_date + timedelta(days=dataset.maturity_days + 55)
    known_label_cutoff = fit_origin - timedelta(days=dataset.maturity_days)
    last_origin = known_label_cutoff - timedelta(days=horizon_days)
    rows: list[list[float]] = []
    targets: list[float] = []
    origin_date = first_origin
    while origin_date <= last_origin:
        context = _history_features(dataset, index, origin_date)
        if context.active_scale_days < MIN_ACTIVE_SCALE_DAYS:
            origin_date += timedelta(days=1)
            continue
        for lead_day in range(1, horizon_days + 1):
            target_date = origin_date + timedelta(days=lead_day)
            rows.append(
                _row(
                    context,
                    lead_day=lead_day,
                    target_date=target_date,
                )
            )
            target_ratio = safe_ratio(
                index.value(target_date, fit_origin),
                context.revenue_scale,
            )
            targets.append(min(MAX_TARGET_RATIO, max(0.0, target_ratio)))
        origin_date += timedelta(days=1)
    if not rows:
        raise ValueError("No leakage-safe training samples are available for M2")
    return rows, targets
