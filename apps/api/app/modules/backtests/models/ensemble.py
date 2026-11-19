from hashlib import sha256
from math import isclose, isfinite

from app.modules.backtests.metrics import aggregate_metrics, calculate_metrics
from app.modules.backtests.types import BacktestResult, FoldResult


DEFAULT_ALPHA_GRID = tuple(value / 10 for value in range(11))
ENSEMBLE_FEATURE_SCHEMA_HASH = sha256(
    b"m4-v1|m2:lightgbm-direct-v3-scaled-stable|m3:orders-aov-v2-decomposition"
).hexdigest()


def build_ensemble_backtest(
    direct: BacktestResult,
    decomposition: BacktestResult,
    alpha_grid: list[float] | tuple[float, ...] = DEFAULT_ALPHA_GRID,
) -> BacktestResult:
    """Select one fixed M2 weight on validation and combine aligned OOF folds."""
    alphas = _normalized_alpha_grid(alpha_grid)
    _validate_aligned_results(direct, decomposition)

    candidates = [
        (_selection_key(result), alpha, result)
        for alpha in alphas
        for result in [_combine_results(direct, decomposition, alpha)]
    ]
    _, selected_alpha, selected = min(
        candidates, key=lambda item: (item[0], item[1])
    )
    return BacktestResult(
        folds=selected.folds,
        metrics=selected.metrics,
        holdout_from=selected.holdout_from,
        holdout_to=selected.holdout_to,
        metadata={
            "selected_alpha": selected_alpha,
            "alpha_grid": list(alphas),
            "selection_metric": "mean_fold_wape_then_mae",
        },
    )


def _normalized_alpha_grid(
    alpha_grid: list[float] | tuple[float, ...],
) -> tuple[float, ...]:
    if not alpha_grid:
        raise ValueError("M4 alpha grid must not be empty")
    normalized = tuple(
        sorted({round(float(alpha), 10) for alpha in alpha_grid})
    )
    if any(
        not isfinite(alpha) or alpha < 0 or alpha > 1
        for alpha in normalized
    ):
        raise ValueError("M4 alpha values must be between 0 and 1")
    return normalized


def _validate_aligned_results(
    direct: BacktestResult, decomposition: BacktestResult
) -> None:
    if (
        direct.holdout_from != decomposition.holdout_from
        or direct.holdout_to != decomposition.holdout_to
    ):
        raise ValueError("M2 and M3 holdout ranges do not match")
    if len(direct.folds) != len(decomposition.folds):
        raise ValueError("M2 and M3 fold counts do not match")
    for direct_fold, decomposition_fold in zip(
        direct.folds, decomposition.folds, strict=True
    ):
        direct_identity = (
            direct_fold.fold_no,
            direct_fold.origin_date,
            direct_fold.train_from,
            direct_fold.train_to,
            direct_fold.test_from,
            direct_fold.test_to,
        )
        decomposition_identity = (
            decomposition_fold.fold_no,
            decomposition_fold.origin_date,
            decomposition_fold.train_from,
            decomposition_fold.train_to,
            decomposition_fold.test_from,
            decomposition_fold.test_to,
        )
        if direct_identity != decomposition_identity:
            raise ValueError("M2 and M3 folds are not aligned")
        if len(direct_fold.predictions) != len(decomposition_fold.predictions):
            raise ValueError("M2 and M3 prediction counts do not match")
        for direct_point, decomposition_point in zip(
            direct_fold.predictions,
            decomposition_fold.predictions,
            strict=True,
        ):
            if direct_point["date"] != decomposition_point["date"] or not isclose(
                float(direct_point["actual"]),
                float(decomposition_point["actual"]),
                rel_tol=0,
                abs_tol=1e-8,
            ):
                raise ValueError("M2 and M3 validation points are not aligned")


def _combine_results(
    direct: BacktestResult,
    decomposition: BacktestResult,
    alpha: float,
) -> BacktestResult:
    folds: list[FoldResult] = []
    for direct_fold, decomposition_fold in zip(
        direct.folds, decomposition.folds, strict=True
    ):
        points: list[dict[str, str | float | None]] = []
        actuals: list[float] = []
        predictions: list[float] = []
        for direct_point, decomposition_point in zip(
            direct_fold.predictions,
            decomposition_fold.predictions,
            strict=True,
        ):
            actual = float(direct_point["actual"])
            predicted_m2 = float(direct_point["predicted"])
            predicted_m3 = float(decomposition_point["predicted"])
            predicted = max(
                0.0,
                alpha * predicted_m2 + (1 - alpha) * predicted_m3,
            )
            actuals.append(actual)
            predictions.append(predicted)
            points.append(
                {
                    "date": str(direct_point["date"]),
                    "actual": actual,
                    "predicted": predicted,
                    "predicted_m2": predicted_m2,
                    "predicted_m3": predicted_m3,
                    "ensemble_alpha": alpha,
                }
            )
        folds.append(
            FoldResult(
                fold_no=direct_fold.fold_no,
                origin_date=direct_fold.origin_date,
                train_from=direct_fold.train_from,
                train_to=direct_fold.train_to,
                test_from=direct_fold.test_from,
                test_to=direct_fold.test_to,
                metrics=calculate_metrics(actuals, predictions),
                predictions=points,
            )
        )
    return BacktestResult(
        folds=folds,
        metrics=aggregate_metrics(folds),
        holdout_from=direct.holdout_from,
        holdout_to=direct.holdout_to,
    )


def _selection_key(result: BacktestResult) -> tuple[float, float]:
    wape = result.metrics["wape_mean"]
    mae = float(result.metrics["mae_mean"] or 0)
    return (float(wape) if wape is not None else float("inf"), mae)
