from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utc_now
from app.db.models import AuditEvent, ModelRun, ModelRunStatus, User
from app.modules.backtests.engine import (
    run_rolling_backtest,
    split_development_holdout,
)
from app.modules.backtests.models.sarima import SarimaModel
from app.modules.backtests.models.seasonal_naive import SeasonalNaiveModel
from app.modules.backtests.queue import BacktestDispatcher
from app.modules.backtests.repository import BacktestRepository
from app.modules.backtests.schemas import (
    AggregateMetricsResponse,
    BacktestFoldResponse,
    BacktestRequest,
    BacktestRunResponse,
    FoldMetricsResponse,
    PredictionPointResponse,
)
from app.modules.backtests.types import BacktestResult, FoldExecutionError


class BacktestService:
    def __init__(
        self,
        session: Session,
        dispatcher: BacktestDispatcher | None = None,
    ) -> None:
        self.session = session
        self.repository = BacktestRepository(session)
        self.dispatcher = dispatcher

    def enqueue(
        self, request: BacktestRequest, user: User
    ) -> BacktestRunResponse:
        snapshot = self.repository.ready_snapshot(request.dataset_fingerprint)
        if snapshot is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="READY_DATASET_SNAPSHOT_NOT_FOUND",
                message="A ready dataset snapshot was not found",
            )
        series = self.repository.mature_revenue_series(snapshot.id)
        try:
            _, holdout = split_development_holdout(
                series,
                horizon_days=request.horizon_days,
                holdout_days=request.holdout_days,
                min_train_days=request.min_train_days,
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
            model_code=request.model_code,
            target="revenue",
            horizon_days=request.horizon_days,
            status=ModelRunStatus.QUEUED.value,
            config_json=request.model_dump(mode="json"),
            holdout_from=holdout[0].date,
            holdout_to=holdout[-1].date,
            created_by_id=user.id,
        )
        self.session.add(run)
        self.session.commit()

        if self.dispatcher is None:
            raise RuntimeError("A backtest dispatcher is required to enqueue a run")
        try:
            run.job_id = self.dispatcher.enqueue(run.id)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            failed_run = self.repository.get_run(run.id)
            assert failed_run is not None
            failed_run.status = ModelRunStatus.FAILED.value
            failed_run.error_json = {
                "code": "QUEUE_UNAVAILABLE",
                "message": str(exc),
                "stage": "enqueue",
                "fold_no": None,
            }
            failed_run.completed_at = utc_now()
            self.session.commit()
            raise AppError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="BACKTEST_QUEUE_UNAVAILABLE",
                message="The model worker queue is unavailable",
            ) from exc
        persisted_run = self.repository.get_run(run.id)
        assert persisted_run is not None
        return self._response(persisted_run)

    def execute_run(self, run_id: int) -> BacktestRunResponse:
        run = self.repository.get_run(run_id)
        if run is None:
            raise ValueError(f"Model run {run_id} was not found")
        if run.status == ModelRunStatus.SUCCEEDED.value:
            return self._response(run)
        if run.status != ModelRunStatus.QUEUED.value:
            raise ValueError(
                f"Model run {run_id} cannot start from status {run.status}"
            )

        run.status = ModelRunStatus.RUNNING.value
        run.started_at = utc_now()
        run.error_json = None
        self.session.commit()

        try:
            request = BacktestRequest.model_validate(run.config_json)
            series = self.repository.mature_revenue_series(run.snapshot_id)
            result = self._execute_model(request, series)
            self._persist_result(run, result)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            failed_run = self.repository.get_run(run_id)
            assert failed_run is not None
            failed_run.status = ModelRunStatus.FAILED.value
            failed_run.error_json = {
                "code": "BACKTEST_FOLD_FAILED"
                if isinstance(exc, FoldExecutionError)
                else "BACKTEST_FAILED",
                "message": str(exc),
                "stage": "fold" if isinstance(exc, FoldExecutionError) else "run",
                "fold_no": getattr(exc, "fold_no", None),
                "error_type": type(exc).__name__,
            }
            failed_run.completed_at = utc_now()
            self.session.commit()
            raise

        persisted_run = self.repository.get_run(run_id)
        assert persisted_run is not None
        return self._response(persisted_run)

    @staticmethod
    def _execute_model(request: BacktestRequest, series) -> BacktestResult:
        if request.model_code == "M0":
            model = SeasonalNaiveModel(
                season_length=request.season_length,
            )
        else:
            model = SarimaModel(
                order=request.sarima_order,
                seasonal_order=request.sarima_seasonal_order,
                maxiter=request.sarima_maxiter,
            )
        return run_rolling_backtest(
            series,
            model=model,
            horizon_days=request.horizon_days,
            holdout_days=request.holdout_days,
            min_train_days=request.min_train_days,
            step_days=request.step_days,
        )

    def _persist_result(self, run: ModelRun, result: BacktestResult) -> None:
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
                actor_id=run.created_by_id,
                action="model.backtest_completed",
                entity_type="model_run",
                entity_id=str(run.id),
                payload_json={
                    "model_code": run.model_code,
                    "dataset_fingerprint": run.dataset_fingerprint,
                    "fold_count": len(result.folds),
                    "horizon_days": run.horizon_days,
                },
            )
        )

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
        metrics = run.metrics_json
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
            metrics=(AggregateMetricsResponse(**metrics) if metrics else None),
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
            job_id=run.job_id,
            error=run.error_json,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
