from decimal import Decimal

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import BacktestFold, DailySale, DatasetSnapshot, ModelRun
from app.modules.backtests.types import SeriesPoint


class BacktestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ready_snapshot(self, fingerprint: str | None) -> DatasetSnapshot | None:
        statement = select(DatasetSnapshot).where(DatasetSnapshot.status == "ready")
        if fingerprint is not None:
            statement = statement.where(
                DatasetSnapshot.fingerprint == fingerprint
            )
        return self.session.scalar(
            statement.order_by(
                DatasetSnapshot.created_at.desc(), DatasetSnapshot.id.desc()
            ).limit(1)
        )

    def mature_revenue_series(self, snapshot_id: int) -> list[SeriesPoint]:
        rows = self.session.execute(
            select(DailySale.sales_date, DailySale.sales_value)
            .where(
                DailySale.snapshot_id == snapshot_id,
                DailySale.is_mature.is_(True),
            )
            .order_by(DailySale.sales_date)
        ).all()
        return [SeriesPoint(date=row[0], value=float(row[1])) for row in rows]

    def get_run(self, run_id: int) -> ModelRun | None:
        return self.session.scalar(
            select(ModelRun)
            .where(ModelRun.id == run_id)
            .options(selectinload(ModelRun.folds))
        )

    def latest_run(self, model_code: str) -> ModelRun | None:
        return self.session.scalar(
            select(ModelRun)
            .where(ModelRun.model_code == model_code)
            .order_by(ModelRun.created_at.desc(), ModelRun.id.desc())
            .limit(1)
            .options(selectinload(ModelRun.folds))
        )

    def latest_matching_run(
        self,
        *,
        model_code: str,
        dataset_fingerprint: str | None = None,
        horizon_days: int | None = None,
        holdout_days: int | None = None,
        min_train_days: int | None = None,
        step_days: int | None = None,
        season_length: int | None = None,
        sarima_maxiter: int | None = None,
    ) -> ModelRun | None:
        statement = select(ModelRun).where(ModelRun.model_code == model_code)
        if dataset_fingerprint is not None:
            statement = statement.where(
                ModelRun.dataset_fingerprint == dataset_fingerprint
            )
        if horizon_days is not None:
            statement = statement.where(ModelRun.horizon_days == horizon_days)
        for name, value in (
            ("holdout_days", holdout_days),
            ("min_train_days", min_train_days),
            ("step_days", step_days),
            ("season_length", season_length),
            ("sarima_maxiter", sarima_maxiter),
        ):
            if value is not None:
                statement = statement.where(
                    ModelRun.config_json[name].as_integer() == value
                )
        return self.session.scalar(
            statement.order_by(ModelRun.created_at.desc(), ModelRun.id.desc())
            .limit(1)
            .options(selectinload(ModelRun.folds))
        )

    def run_by_experiment_key(self, experiment_key: str) -> ModelRun | None:
        return self.session.scalar(
            select(ModelRun)
            .where(ModelRun.experiment_key == experiment_key)
            .options(selectinload(ModelRun.folds))
        )

    def stale_running_runs(self, cutoff: datetime) -> list[ModelRun]:
        return list(
            self.session.scalars(
                select(ModelRun).where(
                    ModelRun.status == "running",
                    ModelRun.started_at.is_not(None),
                    ModelRun.started_at < cutoff,
                )
            ).all()
        )

    def add_fold(
        self,
        *,
        run_id: int,
        fold_no: int,
        origin_date,
        train_from,
        train_to,
        test_from,
        test_to,
        mae: float,
        rmse: float,
        wape: float | None,
        actual_sum: float,
        prediction_sum: float,
        predictions: list[dict[str, str | float]],
    ) -> None:
        self.session.add(
            BacktestFold(
                run_id=run_id,
                fold_no=fold_no,
                origin_date=origin_date,
                train_from=train_from,
                train_to=train_to,
                test_from=test_from,
                test_to=test_to,
                mae=Decimal(str(mae)),
                rmse=Decimal(str(rmse)),
                wape=Decimal(str(wape)) if wape is not None else None,
                actual_sum=Decimal(str(actual_sum)),
                prediction_sum=Decimal(str(prediction_sum)),
                predictions_json=predictions,
            )
        )
