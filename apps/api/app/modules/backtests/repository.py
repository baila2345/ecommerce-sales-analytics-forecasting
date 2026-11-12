from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import BacktestFold, DailySale, DatasetSnapshot, ModelRun
from app.modules.backtests.seasonal_naive import SeriesPoint


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
