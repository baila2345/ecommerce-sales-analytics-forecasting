from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utc_now
from app.db.models import (
    AuditEvent,
    DailySale,
    DatasetSnapshot,
    DatasetSnapshotStatus,
    User,
)
from app.modules.data_quality.repository import DataQualityRepository
from app.modules.data_quality.service import DataQualityService
from app.modules.datasets.fingerprint import (
    REQUIRED_DATASET_TYPES,
    FingerprintDescriptor,
    build_fingerprint,
)
from app.modules.datasets.repository import DatasetFoundationRepository
from app.modules.datasets.schemas import (
    DatasetFingerprintResponse,
    DatasetSnapshotResponse,
)


class DatasetFoundationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DatasetFoundationRepository(session)

    def fingerprint(self, maturity_days: int) -> DatasetFingerprintResponse:
        descriptor = self._fingerprint_descriptor(maturity_days)
        return DatasetFingerprintResponse(**descriptor.__dict__)

    def rebuild_daily_sales(
        self,
        maturity_days: int,
        user: User,
    ) -> DatasetSnapshotResponse:
        descriptor = self._fingerprint_descriptor(maturity_days)
        quality_report = DataQualityService(
            DataQualityRepository(self.session)
        ).report()
        if not quality_report.ml_eligibility.ready_for_daily_sales:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="DATASET_QUALITY_GATE_FAILED",
                message="The imported dataset is not eligible for daily sales",
                details={
                    "quality_status": quality_report.status,
                    "ml_eligibility": quality_report.ml_eligibility.model_dump(),
                },
            )

        max_eligible_purchase_date = self.repository.max_eligible_purchase_date()
        if max_eligible_purchase_date is None:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="DATASET_ELIGIBLE_ORDERS_EMPTY",
                message="No eligible delivered orders are available",
            )
        mature_until = min(
            descriptor.source_max_date - timedelta(days=descriptor.maturity_days),
            max_eligible_purchase_date,
        )
        snapshot = self.repository.prepare_snapshot(
            descriptor,
            mature_until=mature_until,
            quality_report=quality_report.model_dump(mode="json"),
        )
        aggregates = self.repository.aggregate_eligible_sales()
        rows = self._complete_calendar(
            snapshot.id,
            descriptor,
            mature_until,
            aggregates,
        )
        self.repository.replace_daily_sales(snapshot.id, rows)
        self.repository.mark_other_ready_snapshots_stale(snapshot.id)
        snapshot.status = DatasetSnapshotStatus.READY.value
        snapshot.completed_at = utc_now()
        self.session.add(
            AuditEvent(
                actor_id=user.id,
                action="dataset.daily_sales_rebuilt",
                entity_type="dataset_snapshot",
                entity_id=str(snapshot.id),
                payload_json={
                    "fingerprint": snapshot.fingerprint,
                    "maturity_days": snapshot.maturity_days,
                    "daily_sales_days": len(rows),
                },
            )
        )
        self.session.flush()
        response = self._snapshot_response(snapshot)
        self.session.commit()
        return response

    def latest_snapshot(self) -> DatasetSnapshotResponse:
        snapshot = self.repository.latest_snapshot()
        if snapshot is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="DATASET_SNAPSHOT_NOT_FOUND",
                message="No dataset snapshot has been built",
            )
        return self._snapshot_response(snapshot)

    def _fingerprint_descriptor(self, maturity_days: int) -> FingerprintDescriptor:
        checksums = self.repository.latest_completed_checksums()
        missing = [
            dataset_type
            for dataset_type in REQUIRED_DATASET_TYPES
            if dataset_type not in checksums
        ]
        if missing:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="DATASET_IMPORTS_INCOMPLETE",
                message="All nine Olist datasets must be imported first",
                details={"missing_datasets": missing},
            )
        source_min_date, source_max_date = self.repository.source_date_range()
        if source_min_date is None or source_max_date is None:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="DATASET_DATE_RANGE_EMPTY",
                message="Orders do not contain a usable purchase date range",
            )
        return build_fingerprint(
            checksums,
            maturity_days=maturity_days,
            source_min_date=source_min_date,
            source_max_date=source_max_date,
        )

    @staticmethod
    def _complete_calendar(
        snapshot_id: int,
        descriptor: FingerprintDescriptor,
        mature_until: date,
        aggregates: dict[date, dict[str, Decimal | int]],
    ) -> list[DailySale]:
        rows: list[DailySale] = []
        current_date = descriptor.source_min_date
        while current_date <= descriptor.source_max_date:
            aggregate = aggregates.get(current_date)
            sales_value = (
                Decimal(aggregate["sales_value"])
                if aggregate is not None
                else Decimal("0")
            )
            orders_count = (
                int(aggregate["orders_count"]) if aggregate is not None else 0
            )
            aov = (
                (sales_value / orders_count).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if orders_count
                else None
            )
            rows.append(
                DailySale(
                    snapshot_id=snapshot_id,
                    sales_date=current_date,
                    sales_value=sales_value,
                    orders_count=orders_count,
                    customer_count=(
                        int(aggregate["customer_count"])
                        if aggregate is not None
                        else 0
                    ),
                    items_count=(
                        int(aggregate["items_count"])
                        if aggregate is not None
                        else 0
                    ),
                    aov=aov,
                    is_mature=current_date <= mature_until,
                )
            )
            current_date += timedelta(days=1)
        return rows

    def _snapshot_response(
        self, snapshot: DatasetSnapshot
    ) -> DatasetSnapshotResponse:
        summary = self.repository.snapshot_summary(snapshot.id)
        return DatasetSnapshotResponse(
            id=snapshot.id,
            fingerprint=snapshot.fingerprint,
            status=snapshot.status,
            source_checksums=snapshot.source_checksums,
            rules_version=snapshot.rules_version,
            quality_policy_version=snapshot.quality_policy_version,
            source_timezone=snapshot.source_timezone,
            maturity_days=snapshot.maturity_days,
            source_min_date=snapshot.source_min_date,
            source_max_date=snapshot.source_max_date,
            mature_until=snapshot.mature_until,
            daily_sales_days=int(summary["daily_sales_days"]),
            mature_days=int(summary["mature_days"]),
            sales_value=float(summary["sales_value"]),
            orders_count=int(summary["orders_count"]),
            customer_days=int(summary["customer_days"]),
            items_count=int(summary["items_count"]),
            created_at=snapshot.created_at,
            completed_at=snapshot.completed_at,
        )
