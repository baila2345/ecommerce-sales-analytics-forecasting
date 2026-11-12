from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class ModelRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        CheckConstraint(
            "model_code IN ('M0', 'M1', 'M2', 'M3', 'M4')",
            name="model_code",
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="status",
        ),
        CheckConstraint("horizon_days IN (7, 30)", name="horizon_days"),
        Index("ix_model_runs_snapshot_created", "snapshot_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dataset_fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    model_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(30), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    holdout_from: Mapped[date] = mapped_column(Date, nullable=False)
    holdout_to: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    folds: Mapped[list["BacktestFold"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BacktestFold.fold_no",
    )


class BacktestFold(Base):
    __tablename__ = "backtest_folds"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "fold_no", name="uq_backtest_folds_run_fold"
        ),
        CheckConstraint("fold_no >= 1", name="positive_fold_no"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("model_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fold_no: Mapped[int] = mapped_column(Integer, nullable=False)
    origin_date: Mapped[date] = mapped_column(Date, nullable=False)
    train_from: Mapped[date] = mapped_column(Date, nullable=False)
    train_to: Mapped[date] = mapped_column(Date, nullable=False)
    test_from: Mapped[date] = mapped_column(Date, nullable=False)
    test_to: Mapped[date] = mapped_column(Date, nullable=False)
    mae: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    rmse: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    wape: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    actual_sum: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    prediction_sum: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    predictions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False
    )

    run: Mapped[ModelRun] = relationship(back_populates="folds")
