from datetime import date, timedelta

from app.modules.backtests.datasets import RevenueAsOfIndex
from app.modules.backtests.engine import run_temporal_rolling_backtest
from app.modules.backtests.features.direct_decomposition import (
    build_decomposition_training_data,
)
from app.modules.backtests.models.orders_aov import OrdersAovModel
from app.modules.backtests.metrics import calculate_decomposition_metrics
from app.modules.backtests.types import BacktestDataset, RevenueEvent, SeriesPoint


def make_decomposition_dataset(days: int = 600) -> BacktestDataset:
    start = date(2020, 1, 1)
    actuals: list[SeriesPoint] = []
    events: list[RevenueEvent] = []
    for day_index in range(days):
        purchase_date = start + timedelta(days=day_index)
        orders = 10 + day_index % 7
        aov = 80.0 + (day_index % 12) * 2
        actuals.append(SeriesPoint(purchase_date, orders * aov))
        events.extend(
            RevenueEvent(
                purchase_date=purchase_date,
                delivered_date=purchase_date + timedelta(days=5),
                value=aov,
            )
            for _ in range(orders)
        )
    return BacktestDataset(actuals, events, maturity_days=30)


def test_as_of_index_reconciles_orders_aov_and_revenue() -> None:
    purchase_date = date(2020, 1, 1)
    index = RevenueAsOfIndex(
        [
            RevenueEvent(purchase_date, date(2020, 1, 5), 100.0),
            RevenueEvent(purchase_date, date(2020, 1, 10), 200.0),
        ]
    )

    assert index.order_count(purchase_date, date(2020, 1, 4)) == 0
    assert index.aov(purchase_date, date(2020, 1, 4)) is None
    assert index.order_count(purchase_date, date(2020, 1, 7)) == 1
    assert index.aov(purchase_date, date(2020, 1, 7)) == 100
    assert index.order_count(purchase_date, date(2020, 1, 12)) == 2
    assert index.aov(purchase_date, date(2020, 1, 12)) == 150
    assert index.value(purchase_date, date(2020, 1, 12)) == 300


def test_m3_training_excludes_missing_aov_targets() -> None:
    dataset = make_decomposition_dataset()
    missing_date = dataset.actuals[200].date
    events = [
        event
        for event in dataset.revenue_events
        if event.purchase_date != missing_date
    ]
    changed = BacktestDataset(dataset.actuals, events, dataset.maturity_days)

    training = build_decomposition_training_data(
        changed,
        RevenueAsOfIndex(events),
        changed.actuals[394].date,
        horizon_days=30,
    )

    assert len(training.aov_rows) < len(training.orders_rows)
    assert len(training.aov_rows) == len(training.aov_targets)
    assert len(training.orders_rows) == len(training.orders_targets)


def test_m3_is_deterministic_nonnegative_and_reconciles_components() -> None:
    dataset = make_decomposition_dataset()
    origin_date = dataset.actuals[394].date
    forecast_dates = [origin_date + timedelta(days=value) for value in range(1, 8)]
    model = OrdersAovModel(n_estimators=50, seed=42)
    index = RevenueAsOfIndex(dataset.revenue_events)

    first = model.forecast(dataset, index, origin_date, forecast_dates)
    second = model.forecast(dataset, index, origin_date, forecast_dates)

    assert first == second
    assert first.components is not None
    assert all(value >= 0 for value in first.predictions)
    for prediction, component in zip(
        first.predictions,
        first.components,
        strict=True,
    ):
        assert component["predicted_orders"] >= 0
        assert component["predicted_aov"] >= 0
        assert prediction == (
            component["predicted_orders"] * component["predicted_aov"]
        )


def test_m3_backtest_persists_components_without_reading_future_actuals() -> None:
    dataset = make_decomposition_dataset()
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
        "model": OrdersAovModel(n_estimators=50, seed=42),
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
    assert original_predictions == [
        point["predicted"]
        for fold in changed_actuals.folds
        for point in fold.predictions
    ]
    assert all(
        "predicted_orders" in point
        and "predicted_aov" in point
        and "actual_orders" in point
        and "actual_aov" in point
        for fold in original.folds
        for point in fold.predictions
    )
    for fold in original.folds:
        for point in fold.predictions:
            assert point["actual"] == (
                float(point["actual_orders"]) * float(point["actual_aov"])
            )
    component_metrics = calculate_decomposition_metrics(
        [point for fold in original.folds for point in fold.predictions]
    )
    assert component_metrics is not None
    assert component_metrics["orders_mae"] >= 0
    assert component_metrics["aov_mae"] >= 0
