from decimal import Decimal

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    BacktestFold,
    DailySale,
    DatasetSnapshot,
    ModelRun,
    Order,
    OrderItem,
)
from app.modules.backtests.types import BacktestDataset, RevenueEvent, SeriesPoint
from app.modules.data_quality.rules import eligible_ml_order_condition


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

    def backtest_dataset(self, snapshot_id: int) -> BacktestDataset:
        snapshot = self.session.get(DatasetSnapshot, snapshot_id)
        if snapshot is None:
            raise ValueError(f"Dataset snapshot {snapshot_id} was not found")
        actuals = self.mature_revenue_series(snapshot_id)
        rows = self.session.execute(
            select(
                func.date(Order.order_purchase_timestamp),
                func.date(Order.order_delivered_customer_date),
                func.sum(OrderItem.price),
            )
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.order_id)
            .where(eligible_ml_order_condition())
            .group_by(
                Order.order_id,
                func.date(Order.order_purchase_timestamp),
                func.date(Order.order_delivered_customer_date),
            )
        ).all()
        events = [
            RevenueEvent(
                purchase_date=_as_date(row[0]),
                delivered_date=_as_date(row[1]),
                value=float(row[2]),
            )
            for row in rows
        ]
        return BacktestDataset(
            actuals=actuals,
            revenue_events=events,
            maturity_days=snapshot.maturity_days,
        )

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
        model_version: str | None = None,
        dataset_fingerprint: str | None = None,
        horizon_days: int | None = None,
        holdout_days: int | None = None,
        min_train_days: int | None = None,
        step_days: int | None = None,
        season_length: int | None = None,
        sarima_maxiter: int | None = None,
        m2_n_estimators: int | None = None,
        m2_learning_rate: float | None = None,
        m2_num_leaves: int | None = None,
        m2_max_depth: int | None = None,
        m2_min_child_samples: int | None = None,
        m2_seed: int | None = None,
        m3_n_estimators: int | None = None,
        m3_learning_rate: float | None = None,
        m3_num_leaves: int | None = None,
        m3_max_depth: int | None = None,
        m3_min_child_samples: int | None = None,
        m3_seed: int | None = None,
        m4_alpha_grid: list[float] | None = None,
    ) -> ModelRun | None:
        statement = select(ModelRun).where(ModelRun.model_code == model_code)
        if model_version is not None:
            statement = statement.where(
                ModelRun.config_json["model_version"].as_string()
                == model_version
            )
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
            ("m2_n_estimators", m2_n_estimators),
            ("m2_num_leaves", m2_num_leaves),
            ("m2_max_depth", m2_max_depth),
            ("m2_min_child_samples", m2_min_child_samples),
            ("m2_seed", m2_seed),
            ("m3_n_estimators", m3_n_estimators),
            ("m3_num_leaves", m3_num_leaves),
            ("m3_max_depth", m3_max_depth),
            ("m3_min_child_samples", m3_min_child_samples),
            ("m3_seed", m3_seed),
        ):
            if value is not None:
                statement = statement.where(
                    ModelRun.config_json[name].as_integer() == value
                )
        if m2_learning_rate is not None:
            statement = statement.where(
                ModelRun.config_json["m2_learning_rate"].as_float()
                == m2_learning_rate
            )
        if m3_learning_rate is not None:
            statement = statement.where(
                ModelRun.config_json["m3_learning_rate"].as_float()
                == m3_learning_rate
            )
        ordered = statement.order_by(
            ModelRun.created_at.desc(), ModelRun.id.desc()
        ).options(selectinload(ModelRun.folds))
        if m4_alpha_grid is None:
            return self.session.scalar(ordered.limit(1))
        candidates = self.session.scalars(ordered)
        for candidate in candidates:
            if m4_alpha_grid is None or candidate.config_json.get(
                "m4_alpha_grid"
            ) == m4_alpha_grid:
                return candidate
        return None

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
        predictions: list[dict[str, str | float | None]],
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


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
