from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import (
    BacktestFold,
    DailySale,
    DatasetSnapshot,
    DatasetSnapshotStatus,
    ModelRun,
    User,
    UserRole,
)
from app.modules.backtests.seasonal_naive import (
    SeriesPoint,
    calculate_metrics,
    run_seasonal_naive_backtest,
    seasonal_naive_forecast,
)
from app.modules.datasets.fingerprint import REQUIRED_DATASET_TYPES


def test_seasonal_naive_does_not_read_future_actual_values() -> None:
    start = date(2020, 1, 1)
    train = [
        SeriesPoint(start + timedelta(days=index), float(index % 7))
        for index in range(30)
    ]
    forecast_dates = [start + timedelta(days=index) for index in range(30, 60)]

    predictions = seasonal_naive_forecast(train, forecast_dates)
    changed_future_actuals = [999999.0 for _ in forecast_dates]

    assert changed_future_actuals != predictions
    assert predictions == seasonal_naive_forecast(train, forecast_dates)
    assert predictions[7:] == predictions[:-7]


def test_backtest_never_uses_the_reserved_holdout() -> None:
    start = date(2020, 1, 1)
    series = [
        SeriesPoint(
            start + timedelta(days=index),
            100.0 + (index % 7) * 10 + index * 0.5,
        )
        for index in range(600)
    ]

    result = run_seasonal_naive_backtest(
        series,
        horizon_days=30,
        holdout_days=90,
        min_train_days=365,
        step_days=30,
    )

    assert len(result.folds) == 4
    assert result.holdout_from == series[-90].date
    assert result.holdout_to == series[-1].date
    assert all(fold.test_to < result.holdout_from for fold in result.folds)


def test_first_fold_predictions_do_not_change_when_future_actuals_change() -> None:
    start = date(2020, 1, 1)
    original = [
        SeriesPoint(start + timedelta(days=index), float(100 + index))
        for index in range(600)
    ]
    changed = [
        point
        if index < 365
        else SeriesPoint(point.date, 999999.0)
        for index, point in enumerate(original)
    ]
    config = {
        "horizon_days": 30,
        "holdout_days": 90,
        "min_train_days": 365,
        "step_days": 30,
    }

    original_result = run_seasonal_naive_backtest(original, **config)
    changed_result = run_seasonal_naive_backtest(changed, **config)

    assert [
        point["predicted"] for point in original_result.folds[0].predictions
    ] == [point["predicted"] for point in changed_result.folds[0].predictions]


def test_wape_is_null_when_actual_sum_is_zero() -> None:
    metrics = calculate_metrics([0.0, 0.0], [10.0, 20.0])

    assert metrics.wape is None


def seed_backtest_snapshot(db_session: Session) -> str:
    user = User(
        email="backtest@example.com",
        password_hash="test-password-hash",
        role=UserRole.ANALYST.value,
    )
    db_session.add(user)
    db_session.flush()
    start = date(2020, 1, 1)
    end = start + timedelta(days=599)
    snapshot = DatasetSnapshot(
        fingerprint="a" * 64,
        status=DatasetSnapshotStatus.READY.value,
        source_checksums={name: "b" * 64 for name in REQUIRED_DATASET_TYPES},
        rules_version="daily-sales-v2",
        quality_policy_version="olist-ml-quality-v1",
        source_timezone="source-local-brazil",
        maturity_days=30,
        source_min_date=start,
        source_max_date=end,
        mature_until=end,
        quality_report={},
        completed_at=datetime(2021, 1, 1),
    )
    db_session.add(snapshot)
    db_session.flush()
    db_session.add_all(
        DailySale(
            snapshot_id=snapshot.id,
            sales_date=start + timedelta(days=index),
            sales_value=Decimal(str(100 + (index % 7) * 10 + index * 0.5)),
            orders_count=1,
            customer_count=1,
            items_count=1,
            aov=Decimal(str(100 + (index % 7) * 10 + index * 0.5)),
            is_mature=True,
        )
        for index in range(600)
    )
    db_session.commit()
    return create_access_token(user.id, user.role)


def test_m0_backtest_endpoint_persists_run_and_folds(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_backtest_snapshot(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/models/backtests",
        headers=headers,
        json={
            "model_code": "M0",
            "dataset_fingerprint": "a" * 64,
            "horizon_days": 30,
            "holdout_days": 90,
            "min_train_days": 365,
            "step_days": 30,
            "season_length": 7,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model_code"] == "M0"
    assert body["status"] == "succeeded"
    assert body["holdout_evaluated"] is False
    assert body["fold_count"] == 4
    assert body["metrics"]["mae_mean"] > 0
    assert len(body["folds"][0]["predictions"]) == 30
    assert all(
        fold["test_to"] < body["holdout_from"] for fold in body["folds"]
    )

    fetched = client.get(f"/api/v1/models/runs/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json() == body
    latest = client.get("/api/v1/models/runs/latest", headers=headers)
    assert latest.status_code == 200
    assert latest.json() == body
    assert db_session.scalar(select(func.count()).select_from(ModelRun)) == 1
    assert db_session.scalar(select(func.count()).select_from(BacktestFold)) == 4
