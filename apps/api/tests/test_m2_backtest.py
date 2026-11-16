from datetime import date, timedelta

import pytest

from app.modules.backtests.datasets import RevenueAsOfIndex, known_series_at
from app.modules.backtests.engine import run_temporal_rolling_backtest
from app.modules.backtests.features.direct_revenue import (
    DIRECT_FEATURE_NAMES,
    build_forecast_matrix,
    build_training_matrix,
)
from app.modules.backtests.models.base import SeriesModelAdapter
from app.modules.backtests.models.lightgbm_direct import LightGBMDirectModel
from app.modules.backtests.models.seasonal_naive import SeasonalNaiveModel
from app.modules.backtests.types import BacktestDataset, RevenueEvent, SeriesPoint


def make_temporal_dataset(days: int = 600) -> BacktestDataset:
    start = date(2020, 1, 1)
    actuals = [
        SeriesPoint(start + timedelta(days=index), float(100 + index % 7))
        for index in range(days)
    ]
    events = [
        RevenueEvent(
            purchase_date=point.date,
            delivered_date=point.date + timedelta(days=5),
            value=point.value,
        )
        for point in actuals
    ]
    return BacktestDataset(actuals, events, maturity_days=30)


def test_as_of_series_excludes_delivery_after_origin() -> None:
    purchase_date = date(2020, 1, 1)
    dataset = BacktestDataset(
        actuals=[SeriesPoint(purchase_date, 150.0)],
        revenue_events=[
            RevenueEvent(purchase_date, date(2020, 2, 15), 150.0)
        ],
        maturity_days=30,
    )
    index = RevenueAsOfIndex(dataset.revenue_events)

    before_delivery = known_series_at(dataset, index, date(2020, 2, 10))
    after_delivery = known_series_at(dataset, index, date(2020, 2, 20))

    assert before_delivery[0].value == 0
    assert after_delivery[0].value == 150


def test_temporal_folds_apply_maturity_and_keep_holdout_locked() -> None:
    dataset = make_temporal_dataset()

    result = run_temporal_rolling_backtest(
        dataset,
        model=SeriesModelAdapter(SeasonalNaiveModel()),
        horizon_days=30,
        holdout_days=90,
        min_train_days=365,
        step_days=30,
    )

    assert len(result.folds) == 3
    assert all(
        fold.train_to == fold.origin_date - timedelta(days=30)
        for fold in result.folds
    )
    assert all(fold.test_to < result.holdout_from for fold in result.folds)


def test_direct_features_do_not_read_future_actuals() -> None:
    dataset = make_temporal_dataset()
    changed = BacktestDataset(
        actuals=[
            point
            if index < 400
            else SeriesPoint(point.date, 999999.0)
            for index, point in enumerate(dataset.actuals)
        ],
        revenue_events=dataset.revenue_events,
        maturity_days=dataset.maturity_days,
    )
    origin = dataset.actuals[394].date
    forecast_dates = [origin + timedelta(days=value) for value in range(1, 31)]

    original_features = build_forecast_matrix(
        dataset,
        RevenueAsOfIndex(dataset.revenue_events),
        origin,
        forecast_dates,
    )
    changed_features = build_forecast_matrix(
        changed,
        RevenueAsOfIndex(changed.revenue_events),
        origin,
        forecast_dates,
    )

    assert original_features == changed_features


def test_direct_training_matrix_has_one_row_per_origin_and_lead() -> None:
    dataset = make_temporal_dataset()
    origin = dataset.actuals[394].date

    rows, targets = build_training_matrix(
        dataset,
        RevenueAsOfIndex(dataset.revenue_events),
        origin,
        horizon_days=30,
    )

    assert len(rows) == len(targets)
    assert len(rows) > 30
    assert len(rows[0]) == len(DIRECT_FEATURE_NAMES)
    assert {int(row[0]) for row in rows} == set(range(1, 31))


def test_m21_targets_are_normalized_by_each_origin_revenue_scale() -> None:
    dataset = make_temporal_dataset()
    scaled = BacktestDataset(
        actuals=[
            SeriesPoint(point.date, point.value * 10)
            for point in dataset.actuals
        ],
        revenue_events=[
            RevenueEvent(
                event.purchase_date,
                event.delivered_date,
                event.value * 10,
            )
            for event in dataset.revenue_events
        ],
        maturity_days=dataset.maturity_days,
    )
    origin = dataset.actuals[394].date

    _, targets = build_training_matrix(
        dataset,
        RevenueAsOfIndex(dataset.revenue_events),
        origin,
        horizon_days=30,
    )
    _, scaled_targets = build_training_matrix(
        scaled,
        RevenueAsOfIndex(scaled.revenue_events),
        origin,
        horizon_days=30,
    )

    assert scaled_targets == targets


def test_m21_marks_black_friday_without_external_data() -> None:
    dataset = make_temporal_dataset()
    origin = date(2020, 11, 20)
    forecast_dates = [date(2020, 11, 27), date(2020, 12, 20)]

    rows = build_forecast_matrix(
        dataset,
        RevenueAsOfIndex(dataset.revenue_events),
        origin,
        forecast_dates,
    )
    window_index = DIRECT_FEATURE_NAMES.index(
        "target_is_black_friday_window"
    )
    distance_index = DIRECT_FEATURE_NAMES.index(
        "target_black_friday_distance"
    )

    assert rows[0][window_index] == 1
    assert rows[0][distance_index] == 0
    assert rows[1][window_index] == 0
    assert rows[1][distance_index] == 15


def test_m21_skips_sparse_origins_and_caps_unstable_target_ratios() -> None:
    dataset = make_temporal_dataset()
    sparse = BacktestDataset(
        actuals=[
            SeriesPoint(point.date, 0.0 if index < 120 else point.value)
            for index, point in enumerate(dataset.actuals)
        ],
        revenue_events=[
            RevenueEvent(
                event.purchase_date,
                event.delivered_date,
                0.0 if index < 120 else event.value,
            )
            for index, event in enumerate(dataset.revenue_events)
        ],
        maturity_days=dataset.maturity_days,
    )
    index = RevenueAsOfIndex(sparse.revenue_events)
    fit_origin = sparse.actuals[394].date

    _, targets = build_training_matrix(
        sparse,
        index,
        fit_origin,
        horizon_days=30,
    )

    assert targets
    assert min(targets) >= 0
    assert max(targets) <= 10
    with pytest.raises(ValueError, match="at least 21 revenue days"):
        build_forecast_matrix(
            sparse,
            index,
            sparse.actuals[100].date,
            [sparse.actuals[101].date],
        )


def test_m2_is_deterministic_nonnegative_and_ignores_changed_future_actuals() -> None:
    dataset = make_temporal_dataset()
    first_test_index = 365 + dataset.maturity_days
    changed = BacktestDataset(
        actuals=[
            point
            if index < first_test_index
            else SeriesPoint(point.date, 999999.0)
            for index, point in enumerate(dataset.actuals)
        ],
        revenue_events=dataset.revenue_events,
        maturity_days=dataset.maturity_days,
    )
    config = {
        "model": LightGBMDirectModel(n_estimators=50, seed=42),
        "horizon_days": 7,
        "holdout_days": 90,
        "min_train_days": 365,
        "step_days": 30,
    }

    original = run_temporal_rolling_backtest(dataset, **config)
    changed_actuals = run_temporal_rolling_backtest(changed, **config)

    original_predictions = [
        point["predicted"]
        for fold in original.folds
        for point in fold.predictions
    ]
    changed_predictions = [
        point["predicted"]
        for fold in changed_actuals.folds
        for point in fold.predictions
    ]
    assert original_predictions == changed_predictions
    assert all(value >= 0 for value in original_predictions)
