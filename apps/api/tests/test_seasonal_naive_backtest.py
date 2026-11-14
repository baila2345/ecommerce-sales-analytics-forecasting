from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.base import utc_now
from app.db.models import (
    BacktestFold,
    DailySale,
    DatasetSnapshot,
    DatasetSnapshotStatus,
    ModelRun,
    ModelRunStatus,
    User,
    UserRole,
)
from app.modules.backtests.metrics import calculate_metrics
from app.modules.backtests.models.sarima import run_sarima_backtest
from app.modules.backtests.models.seasonal_naive import (
    run_seasonal_naive_backtest,
    seasonal_naive_forecast,
)
from app.modules.backtests.queue import get_backtest_dispatcher
from app.modules.backtests.service import BacktestService
from app.modules.backtests.types import FoldExecutionError, SeriesPoint
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


def test_m1_uses_the_same_folds_and_keeps_holdout_locked(monkeypatch) -> None:
    start = date(2020, 1, 1)
    series = [
        SeriesPoint(start + timedelta(days=index), float(100 + index % 7))
        for index in range(600)
    ]
    monkeypatch.setattr(
        "app.modules.backtests.models.sarima.sarima_forecast",
        lambda train, steps, **_kwargs: [float(train[-7])] * steps,
    )
    common = {
        "horizon_days": 30,
        "holdout_days": 90,
        "min_train_days": 365,
        "step_days": 30,
    }

    m0 = run_seasonal_naive_backtest(series, **common)
    m1 = run_sarima_backtest(series, **common)

    assert [fold.test_from for fold in m1.folds] == [
        fold.test_from for fold in m0.folds
    ]
    assert [fold.test_to for fold in m1.folds] == [
        fold.test_to for fold in m0.folds
    ]
    assert m1.holdout_from == m0.holdout_from
    assert all(fold.test_to < m1.holdout_from for fold in m1.folds)


class FakeDispatcher:
    def __init__(self) -> None:
        self.run_ids: list[int] = []

    def enqueue(self, run_id: int) -> str:
        self.run_ids.append(run_id)
        return f"job-{run_id}"


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
    dispatcher = FakeDispatcher()
    client.app.dependency_overrides[get_backtest_dispatcher] = lambda: dispatcher
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

    assert response.status_code == 202
    queued = response.json()
    assert queued["model_code"] == "M0"
    assert queued["status"] == "queued"
    assert queued["metrics"] is None
    assert queued["fold_count"] == 0
    assert queued["job_id"] == f"job-{queued['id']}"
    assert dispatcher.run_ids == [queued["id"]]

    completed = BacktestService(db_session).execute_run(queued["id"])
    body = completed.model_dump(mode="json")
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


def test_m1_fold_failure_is_persisted(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    dispatcher = FakeDispatcher()
    client.app.dependency_overrides[get_backtest_dispatcher] = lambda: dispatcher
    token = seed_backtest_snapshot(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/models/backtests",
        headers=headers,
        json={
            "model_code": "M1",
            "dataset_fingerprint": "a" * 64,
            "horizon_days": 30,
            "holdout_days": 90,
            "min_train_days": 365,
            "step_days": 30,
        },
    )
    run_id = response.json()["id"]
    monkeypatch.setattr(
        "app.modules.backtests.service.run_rolling_backtest",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FoldExecutionError("M1", 2, "optimizer failed")
        ),
    )

    with pytest.raises(FoldExecutionError):
        BacktestService(db_session).execute_run(run_id)

    failed = client.get(f"/api/v1/models/runs/{run_id}", headers=headers)
    assert failed.status_code == 200
    body = failed.json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "BACKTEST_FOLD_FAILED"
    assert body["error"]["fold_no"] == 2
    assert body["completed_at"] is not None


def test_identical_backtest_request_reuses_the_existing_run(
    client: TestClient,
    db_session: Session,
) -> None:
    dispatcher = FakeDispatcher()
    client.app.dependency_overrides[get_backtest_dispatcher] = lambda: dispatcher
    token = seed_backtest_snapshot(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "model_code": "M0",
        "dataset_fingerprint": "a" * 64,
        "horizon_days": 30,
        "holdout_days": 90,
        "min_train_days": 365,
        "step_days": 30,
        "season_length": 7,
    }

    first = client.post("/api/v1/models/backtests", headers=headers, json=payload)
    second = client.post("/api/v1/models/backtests", headers=headers, json=payload)

    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["experiment_key"] == second.json()["experiment_key"]
    assert dispatcher.run_ids == [first.json()["id"]]
    assert db_session.scalar(select(func.count()).select_from(ModelRun)) == 1


def test_stale_running_backtest_is_failed_and_can_be_retried(
    client: TestClient,
    db_session: Session,
) -> None:
    dispatcher = FakeDispatcher()
    client.app.dependency_overrides[get_backtest_dispatcher] = lambda: dispatcher
    token = seed_backtest_snapshot(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "model_code": "M1",
        "dataset_fingerprint": "a" * 64,
        "horizon_days": 30,
        "holdout_days": 90,
        "min_train_days": 365,
        "step_days": 30,
    }
    queued = client.post(
        "/api/v1/models/backtests", headers=headers, json=payload
    ).json()
    run = db_session.get(ModelRun, queued["id"])
    assert run is not None
    run.status = ModelRunStatus.RUNNING.value
    run.started_at = utc_now() - timedelta(minutes=66)
    db_session.commit()

    expired = client.get(
        f"/api/v1/models/runs/{queued['id']}", headers=headers
    )

    assert expired.status_code == 200
    assert expired.json()["status"] == "failed"
    assert expired.json()["error"]["code"] == "STALE_MODEL_RUN"
    assert expired.json()["experiment_key"] is None

    retried = client.post(
        "/api/v1/models/backtests", headers=headers, json=payload
    )
    assert retried.status_code == 202
    assert retried.json()["id"] != queued["id"]


def test_latest_run_can_be_filtered_by_complete_experiment_signature(
    client: TestClient,
    db_session: Session,
) -> None:
    dispatcher = FakeDispatcher()
    client.app.dependency_overrides[get_backtest_dispatcher] = lambda: dispatcher
    token = seed_backtest_snapshot(db_session)
    headers = {"Authorization": f"Bearer {token}"}
    base = {
        "model_code": "M0",
        "dataset_fingerprint": "a" * 64,
        "holdout_days": 90,
        "min_train_days": 365,
        "step_days": 30,
        "season_length": 7,
    }
    h7 = client.post(
        "/api/v1/models/backtests",
        headers=headers,
        json={**base, "horizon_days": 7},
    ).json()
    h30 = client.post(
        "/api/v1/models/backtests",
        headers=headers,
        json={**base, "horizon_days": 30},
    ).json()

    response = client.get(
        "/api/v1/models/runs/latest",
        headers=headers,
        params={
            "model_code": "M0",
            "dataset_fingerprint": "a" * 64,
            "horizon_days": 7,
            "holdout_days": 90,
            "min_train_days": 365,
            "step_days": 30,
            "season_length": 7,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == h7["id"]
    assert response.json()["id"] != h30["id"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sarima_order", [-1, 1, 1]),
        ("sarima_order", [6, 1, 1]),
        ("sarima_seasonal_order", [1, 0, 1, 1]),
        ("sarima_seasonal_order", [4, 0, 1, 7]),
    ],
)
def test_invalid_sarima_parameters_are_rejected_before_queueing(
    client: TestClient,
    db_session: Session,
    field: str,
    value: list[int],
) -> None:
    dispatcher = FakeDispatcher()
    client.app.dependency_overrides[get_backtest_dispatcher] = lambda: dispatcher
    token = seed_backtest_snapshot(db_session)

    response = client.post(
        "/api/v1/models/backtests",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "model_code": "M1",
            "dataset_fingerprint": "a" * 64,
            field: value,
        },
    )

    assert response.status_code == 422
    assert dispatcher.run_ids == []
