from datetime import date, timedelta

import pytest

from app.modules.backtests.metrics import aggregate_metrics, calculate_metrics
from app.modules.backtests.models.ensemble import build_ensemble_backtest
from app.modules.backtests.schemas import BacktestRequest
from app.modules.backtests.service import BacktestService
from app.modules.backtests.types import (
    BacktestDataset,
    BacktestResult,
    FoldResult,
    RevenueEvent,
    SeriesPoint,
)


def make_branch_result(predicted: float) -> BacktestResult:
    start = date(2020, 1, 1)
    folds: list[FoldResult] = []
    for fold_index in range(3):
        test_date = start + timedelta(days=fold_index * 7)
        actuals = [10.0, 10.0]
        predictions = [predicted, predicted]
        folds.append(
            FoldResult(
                fold_no=fold_index + 1,
                origin_date=test_date - timedelta(days=1),
                train_from=start - timedelta(days=100),
                train_to=test_date - timedelta(days=30),
                test_from=test_date,
                test_to=test_date + timedelta(days=1),
                metrics=calculate_metrics(actuals, predictions),
                predictions=[
                    {
                        "date": (test_date + timedelta(days=offset)).isoformat(),
                        "actual": actual,
                        "predicted": prediction,
                    }
                    for offset, (actual, prediction) in enumerate(
                        zip(actuals, predictions, strict=True)
                    )
                ],
            )
        )
    return BacktestResult(
        folds=folds,
        metrics=aggregate_metrics(folds),
        holdout_from=date(2020, 3, 1),
        holdout_to=date(2020, 3, 30),
    )


def make_temporal_dataset(days: int = 600) -> BacktestDataset:
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


def test_m4_selects_fixed_alpha_from_validation_and_persists_branches() -> None:
    direct = make_branch_result(8.0)
    decomposition = make_branch_result(12.0)

    first = build_ensemble_backtest(direct, decomposition, [0.0, 0.5, 1.0])
    second = build_ensemble_backtest(direct, decomposition, [1.0, 0.5, 0.0])

    assert first == second
    assert first.metadata == {
        "selected_alpha": 0.5,
        "alpha_grid": [0.0, 0.5, 1.0],
        "selection_metric": "mean_fold_wape_then_mae",
    }
    assert first.metrics["wape_mean"] == 0
    for fold in first.folds:
        for point in fold.predictions:
            assert point == {
                "date": point["date"],
                "actual": 10.0,
                "predicted": 10.0,
                "predicted_m2": 8.0,
                "predicted_m3": 12.0,
                "ensemble_alpha": 0.5,
            }


def test_m4_refuses_misaligned_branch_predictions() -> None:
    direct = make_branch_result(8.0)
    decomposition = make_branch_result(12.0)
    decomposition.folds[0].predictions[0]["date"] = "2099-01-01"

    with pytest.raises(ValueError, match="validation points are not aligned"):
        build_ensemble_backtest(direct, decomposition)


def test_m4_runs_both_leakage_safe_branches_on_the_same_folds() -> None:
    result = BacktestService._execute_model(
        BacktestRequest(
            model_code="M4",
            horizon_days=7,
            holdout_days=90,
            min_train_days=365,
            step_days=30,
            m2_n_estimators=50,
            m3_n_estimators=50,
            m4_alpha_grid=[0.0, 0.5, 1.0],
        ),
        make_temporal_dataset(),
    )

    assert len(result.folds) >= 3
    assert result.metadata["selected_alpha"] in [0.0, 0.5, 1.0]
    for fold in result.folds:
        for point in fold.predictions:
            alpha = float(point["ensemble_alpha"])
            assert float(point["predicted"]) == pytest.approx(
                alpha * float(point["predicted_m2"])
                + (1 - alpha) * float(point["predicted_m3"])
            )
            assert float(point["predicted"]) >= 0


@pytest.mark.parametrize(
    "alpha_grid",
    [
        [],
        [0.0],
        [-0.1, 0.5],
        [0.5, 1.1],
        [0.5, 0.5],
        [0.5, float("nan")],
    ],
)
def test_m4_rejects_invalid_alpha_grid_at_api_boundary(
    alpha_grid: list[float],
) -> None:
    with pytest.raises(ValueError):
        BacktestRequest(model_code="M4", m4_alpha_grid=alpha_grid)
