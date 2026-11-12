from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import case, delete, distinct, func, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    Customer,
    DailySale,
    DatasetSnapshot,
    DatasetSnapshotStatus,
    ImportBatch,
    ImportStatus,
    Order,
    OrderItem,
)
from app.modules.data_quality.rules import eligible_ml_order_condition
from app.modules.datasets.fingerprint import (
    FingerprintDescriptor,
    REQUIRED_DATASET_TYPES,
)


class DatasetFoundationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_completed_checksums(self) -> dict[str, str]:
        checksums: dict[str, str] = {}
        for dataset_type in REQUIRED_DATASET_TYPES:
            checksum = self.session.scalar(
                select(ImportBatch.file_checksum_sha256)
                .where(
                    ImportBatch.dataset_type == dataset_type,
                    ImportBatch.status == ImportStatus.COMPLETED.value,
                )
                .order_by(ImportBatch.completed_at.desc(), ImportBatch.id.desc())
                .limit(1)
            )
            if checksum is not None:
                checksums[dataset_type] = checksum
        return checksums

    def source_date_range(self) -> tuple[date | None, date | None]:
        row = self.session.execute(
            select(
                func.min(Order.order_purchase_timestamp),
                func.max(Order.order_purchase_timestamp),
            )
        ).one()
        return _as_date(row[0]), _as_date(row[1])

    def max_eligible_purchase_date(self) -> date | None:
        value = self.session.scalar(
            select(func.max(Order.order_purchase_timestamp)).where(
                eligible_ml_order_condition()
            )
        )
        return _as_date(value)

    def get_snapshot_by_fingerprint(
        self, fingerprint: str
    ) -> DatasetSnapshot | None:
        return self.session.scalar(
            select(DatasetSnapshot).where(
                DatasetSnapshot.fingerprint == fingerprint
            )
        )

    def latest_snapshot(self) -> DatasetSnapshot | None:
        return self.session.scalar(
            select(DatasetSnapshot)
            .order_by(DatasetSnapshot.created_at.desc(), DatasetSnapshot.id.desc())
            .limit(1)
        )

    def prepare_snapshot(
        self,
        descriptor: FingerprintDescriptor,
        *,
        mature_until: date,
        quality_report: dict,
    ) -> DatasetSnapshot:
        snapshot = self.get_snapshot_by_fingerprint(descriptor.fingerprint)
        if snapshot is None:
            snapshot = DatasetSnapshot(fingerprint=descriptor.fingerprint)
            self.session.add(snapshot)
        snapshot.status = DatasetSnapshotStatus.BUILDING.value
        snapshot.source_checksums = descriptor.source_checksums
        snapshot.rules_version = descriptor.rules_version
        snapshot.quality_policy_version = descriptor.quality_policy_version
        snapshot.source_timezone = descriptor.source_timezone
        snapshot.maturity_days = descriptor.maturity_days
        snapshot.source_min_date = descriptor.source_min_date
        snapshot.source_max_date = descriptor.source_max_date
        snapshot.mature_until = mature_until
        snapshot.quality_report = quality_report
        snapshot.completed_at = None
        self.session.flush()
        return snapshot

    def replace_daily_sales(
        self,
        snapshot_id: int,
        rows: list[DailySale],
    ) -> None:
        self.session.execute(
            delete(DailySale).where(DailySale.snapshot_id == snapshot_id)
        )
        self.session.add_all(rows)

    def aggregate_eligible_sales(self) -> dict[date, dict[str, Decimal | int]]:
        rows = self.session.execute(
            select(
                func.date(Order.order_purchase_timestamp).label("sales_date"),
                func.sum(OrderItem.price).label("sales_value"),
                func.count(distinct(Order.order_id)).label("orders_count"),
                func.count(distinct(Customer.customer_unique_id)).label(
                    "customer_count"
                ),
                func.count(OrderItem.order_id).label("items_count"),
            )
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.order_id)
            .join(Customer, Customer.customer_id == Order.customer_id)
            .where(eligible_ml_order_condition())
            .group_by(func.date(Order.order_purchase_timestamp))
            .order_by(func.date(Order.order_purchase_timestamp))
        ).all()
        return {
            _as_date(row.sales_date): {
                "sales_value": Decimal(row.sales_value),
                "orders_count": int(row.orders_count),
                "customer_count": int(row.customer_count),
                "items_count": int(row.items_count),
            }
            for row in rows
            if _as_date(row.sales_date) is not None
        }

    def snapshot_summary(self, snapshot_id: int) -> dict[str, Decimal | int]:
        row = self.session.execute(
            select(
                func.count(DailySale.sales_date),
                func.coalesce(
                    func.sum(case((DailySale.is_mature.is_(True), 1), else_=0)),
                    0,
                ),
                func.coalesce(func.sum(DailySale.sales_value), Decimal("0")),
                func.coalesce(func.sum(DailySale.orders_count), 0),
                func.coalesce(func.sum(DailySale.customer_count), 0),
                func.coalesce(func.sum(DailySale.items_count), 0),
            ).where(DailySale.snapshot_id == snapshot_id)
        ).one()
        return {
            "daily_sales_days": int(row[0]),
            "mature_days": int(row[1]),
            "sales_value": Decimal(row[2]),
            "orders_count": int(row[3]),
            "customer_days": int(row[4]),
            "items_count": int(row[5]),
        }

    def mark_ready_snapshots_stale(self) -> None:
        self.session.execute(
            update(DatasetSnapshot)
            .where(DatasetSnapshot.status == DatasetSnapshotStatus.READY.value)
            .values(status=DatasetSnapshotStatus.STALE.value)
        )

    def mark_other_ready_snapshots_stale(self, snapshot_id: int) -> None:
        self.session.execute(
            update(DatasetSnapshot)
            .where(
                DatasetSnapshot.status == DatasetSnapshotStatus.READY.value,
                DatasetSnapshot.id != snapshot_id,
            )
            .values(status=DatasetSnapshotStatus.STALE.value)
        )


def _as_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
