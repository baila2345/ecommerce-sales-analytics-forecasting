from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class DatasetSnapshotStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    STALE = "stale"


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('building', 'ready', 'failed', 'stale')",
            name="status",
        ),
        CheckConstraint("maturity_days >= 1", name="positive_maturity_days"),
        Index(
            "ix_dataset_snapshots_fingerprint", "fingerprint", unique=True
        ),
        Index("ix_dataset_snapshots_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DatasetSnapshotStatus.BUILDING.value,
        index=True,
    )
    source_checksums: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    rules_version: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_policy_version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    source_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    maturity_days: Mapped[int] = mapped_column(Integer, nullable=False)
    source_min_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_max_date: Mapped[date] = mapped_column(Date, nullable=False)
    mature_until: Mapped[date] = mapped_column(Date, nullable=False)
    quality_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    daily_sales: Mapped[list["DailySale"]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DailySale(Base):
    __tablename__ = "daily_sales"
    __table_args__ = (
        CheckConstraint("sales_value >= 0", name="non_negative_sales_value"),
        CheckConstraint("orders_count >= 0", name="non_negative_orders_count"),
        CheckConstraint(
            "customer_count >= 0", name="non_negative_customer_count"
        ),
        CheckConstraint("items_count >= 0", name="non_negative_items_count"),
        CheckConstraint("aov IS NULL OR aov >= 0", name="non_negative_aov"),
        Index("ix_daily_sales_snapshot_mature", "snapshot_id", "is_mature"),
    )

    snapshot_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("dataset_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sales_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sales_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aov: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    is_mature: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    snapshot: Mapped[DatasetSnapshot] = relationship(back_populates="daily_sales")
