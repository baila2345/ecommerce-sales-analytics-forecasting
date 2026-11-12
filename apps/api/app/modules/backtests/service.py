from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utc_now
from app.db.models import AuditEvent, ModelRun, ModelRunStatus, User
from app.modules.backtests.repository import BacktestRepository
from app.modules.backtests.schemas import (
    AggregateMetricsResponse,
    BacktestFoldResponse,
    BacktestRequest,
    BacktestRunResponse,
    FoldMetricsResponse,
    PredictionPointResponse,
)
from app.modules.backtests.seasonal_naive import run_seasonal_naive_backtest


class BacktestService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = BacktestRepository(session)

    def run(self, request: BacktestRequest, user: User) -> BacktestRunResponse:
        snapshot = self.repository.ready_snapshot(request.dataset_fingerprint)
        if snapshot is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="READY_DATASET_SNAPSHOT_NOT_FOUND",
                message="A ready dataset snapshot was not found",
            )
        series = self.repository.mature_revenue_series(snapshot.id)
        try:
            result = run_seasonal_naive_backtest(
                series,
                horizon_days=request.horizon_days,
                holdout_days=request.holdout_days,
                min_train_days=request.min_train_days,
                step_days=request.step_days,
                season_length=request.season_length,
            )
        except ValueError as exc:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="INSUFFICIENT_HISTORY",
                message=str(exc),
            ) from exc

        run = ModelRun(
            snapshot_id=snapshot.id,
            dataset_fingerprint=snapshot.fingerprint,
            model_code="M0",
            target="revenue",
            horizon_days=request.horizon_days,
            status=ModelRunStatus.RUNNING.value,
            config_json=request.model_dump(),
            holdout_from=result.holdout_from,
            holdout_to=result.holdout_to,
            created_by_id=user.id,
        )
        self.session.add(run)
        self.session.flush()
        for fold in result.folds:
            self.repository.add_fold(
                run_id=run.id,
                fold_no=fold.fold_no,
                origin_date=fold.origin_date,
                train_from=fold.train_from,
                train_to=fold.train_to,
                test_from=fold.test_from,
                test_to=fold.test_to,
                mae=fold.metrics.mae,
                rmse=fold.metrics.rmse,
                wape=fold.metrics.wape,
                actual_sum=fold.metrics.actual_sum,
                prediction_sum=fold.metrics.prediction_sum,
                predictions=fold.predictions,
            )
        run.metrics_json = result.metrics
        run.status = ModelRunStatus.SUCCEEDED.value
        run.completed_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_id=user.id,
                action="model.backtest_completed",
                entity_type="model_run",
                entity_id=str(run.id),
                payload_json={
                    "model_code": "M0",
                    "dataset_fingerprint": snapshot.fingerprint,
                    "fold_count": len(result.folds),
                    "horizon_days": request.horizon_days,
                },
            )
        )
        self.session.commit()
        persisted_run = self.repository.get_run(run.id)
        assert persisted_run is not None
        return self._response(persisted_run)

    def get_run(self, run_id: int) -> BacktestRunResponse:
        run = self.repository.get_run(run_id)
        if run is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODEL_RUN_NOT_FOUND",
                message="Model run was not found",
            )
        return self._response(run)

    def latest_run(self, model_code: str = "M0") -> BacktestRunResponse:
        run = self.repository.latest_run(model_code)
        if run is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODEL_RUN_NOT_FOUND",
                message="Model run was not found",
            )
        return self._response(run)

    @staticmethod
    def _response(run: ModelRun) -> BacktestRunResponse:
        metrics = run.metrics_json or {}
        return BacktestRunResponse(
            id=run.id,
            model_code=run.model_code,
            status=run.status,
            dataset_fingerprint=run.dataset_fingerprint,
            snapshot_id=run.snapshot_id,
            horizon_days=run.horizon_days,
            holdout_from=run.holdout_from,
            holdout_to=run.holdout_to,
            holdout_evaluated=False,
            fold_count=len(run.folds),
            metrics=AggregateMetricsResponse(**metrics),
            folds=[
                BacktestFoldResponse(
                    fold_no=fold.fold_no,
                    origin_date=fold.origin_date,
                    train_from=fold.train_from,
                    train_to=fold.train_to,
                    test_from=fold.test_from,
                    test_to=fold.test_to,
                    metrics=FoldMetricsResponse(
                        mae=float(fold.mae),
                        rmse=float(fold.rmse),
                        wape=float(fold.wape) if fold.wape is not None else None,
                        actual_sum=float(fold.actual_sum),
                        prediction_sum=float(fold.prediction_sum),
                    ),
                    predictions=[
                        PredictionPointResponse(**point)
                        for point in fold.predictions_json
                    ],
                )
                for fold in run.folds
            ],
            created_at=run.created_at,
            completed_at=run.completed_at,
        )
