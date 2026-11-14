from datetime import timedelta
from hashlib import sha256
import json

from fastapi import status
from sqlalchemy.exc import IntegrityError
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
    MODEL_VERSIONS = {"M0": "seasonal-naive-v1", "M1": "sarima-v1"}
    RUN_TIMEOUT = timedelta(minutes=65)

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
        if self.dispatcher is None:
            raise RuntimeError("A backtest dispatcher is required to enqueue a run")
        self._expire_stale_runs()
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

        experiment_key = self._experiment_key(snapshot.fingerprint, request)
        existing = self.repository.run_by_experiment_key(experiment_key)
        if existing is not None:
            return self._response(existing)

        run = ModelRun(
            snapshot_id=snapshot.id,
            dataset_fingerprint=snapshot.fingerprint,
            model_code=request.model_code,
            target="revenue",
            horizon_days=request.horizon_days,
            status=ModelRunStatus.QUEUED.value,
            config_json=request.model_dump(mode="json"),
            experiment_key=experiment_key,
            holdout_from=holdout[0].date,
            holdout_to=holdout[-1].date,
            created_by_id=user.id,
        )
        self.session.add(run)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.repository.run_by_experiment_key(experiment_key)
            if existing is None:
                raise
            return self._response(existing)

        try:
            run.job_id = self.dispatcher.enqueue(run.id)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            failed_run = self.repository.get_run(run.id)
            assert failed_run is not None
            failed_run.status = ModelRunStatus.FAILED.value
            failed_run.experiment_key = None
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
            failed_run.experiment_key = None
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
        self._expire_stale_runs()
        run = self.repository.get_run(run_id)
        if run is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODEL_RUN_NOT_FOUND",
                message="Model run was not found",
            )
        return self._response(run)

    def latest_run(
        self,
        model_code: str = "M0",
        *,
        dataset_fingerprint: str | None = None,
        horizon_days: int | None = None,
        holdout_days: int | None = None,
        min_train_days: int | None = None,
        step_days: int | None = None,
        season_length: int | None = None,
        sarima_maxiter: int | None = None,
    ) -> BacktestRunResponse:
        self._expire_stale_runs()
        run = self.repository.latest_matching_run(
            model_code=model_code,
            dataset_fingerprint=dataset_fingerprint,
            horizon_days=horizon_days,
            holdout_days=holdout_days,
            min_train_days=min_train_days,
            step_days=step_days,
            season_length=season_length,
            sarima_maxiter=sarima_maxiter,
        )
        if run is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MODEL_RUN_NOT_FOUND",
                message="Model run was not found",
            )
        return self._response(run)

    def _expire_stale_runs(self) -> None:
        cutoff = utc_now() - self.RUN_TIMEOUT
        stale_runs = self.repository.stale_running_runs(cutoff)
        if not stale_runs:
            return
        for run in stale_runs:
            run.status = ModelRunStatus.FAILED.value
            run.experiment_key = None
            run.completed_at = utc_now()
            run.error_json = {
                "code": "STALE_MODEL_RUN",
                "message": "The worker did not finish this run before its timeout",
                "stage": "worker",
                "fold_no": None,
            }
        self.session.commit()

    @classmethod
    def _experiment_key(
        cls, dataset_fingerprint: str, request: BacktestRequest
    ) -> str:
        common = {
            "dataset_fingerprint": dataset_fingerprint,
            "model_code": request.model_code,
            "model_version": cls.MODEL_VERSIONS[request.model_code],
            "horizon_days": request.horizon_days,
            "holdout_days": request.holdout_days,
            "min_train_days": request.min_train_days,
            "step_days": request.step_days,
        }
        if request.model_code == "M0":
            common["season_length"] = request.season_length
        else:
            common.update(
                {
                    "sarima_order": request.sarima_order,
                    "sarima_seasonal_order": request.sarima_seasonal_order,
                    "sarima_maxiter": request.sarima_maxiter,
                }
            )
        canonical = json.dumps(common, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

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
            holdout_days=int(run.config_json["holdout_days"]),
            min_train_days=int(run.config_json["min_train_days"]),
            step_days=int(run.config_json["step_days"]),
            experiment_key=run.experiment_key,
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
