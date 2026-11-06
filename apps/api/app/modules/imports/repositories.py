from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import (
    AuditEvent,
    ImportBatch,
    ImportError,
    ImportStatus,
    ProductCategory,
)
from app.modules.imports.domain import ProductCategoryRow, ValidationIssue


class ImportBatchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        dataset_type: str,
        filename: str,
        checksum_sha256: str,
        user_id: int,
        total_rows: int,
        valid_rows: int,
        rejected_rows: int,
        status: str,
        error_summary: dict[str, Any] | None,
        completed_at: datetime | None,
    ) -> ImportBatch:
        batch = ImportBatch(
            dataset_type=dataset_type,
            original_filename=filename,
            file_checksum_sha256=checksum_sha256,
            status=status,
            total_rows=total_rows,
            valid_rows=valid_rows,
            rejected_rows=rejected_rows,
            uploaded_by_id=user_id,
            error_summary=error_summary,
            completed_at=completed_at,
        )
        self.session.add(batch)
        self.session.flush()
        return batch

    def add_validation_issues(
        self,
        batch_id: int,
        issues: list[ValidationIssue],
    ) -> None:
        self.session.add_all(
            [
                ImportError(
                    batch_id=batch_id,
                    row_number=issue.row_number,
                    field_name=issue.field_name,
                    error_code=issue.code,
                    error_message=issue.message,
                )
                for issue in issues
            ]
        )

    def get_for_update(self, batch_id: int) -> ImportBatch | None:
        return self.session.scalar(
            select(ImportBatch)
            .where(ImportBatch.id == batch_id)
            .with_for_update()
        )

    def get(self, batch_id: int) -> ImportBatch | None:
        return self.session.get(ImportBatch, batch_id)

    @staticmethod
    def mark_processing(batch: ImportBatch) -> None:
        batch.status = ImportStatus.PROCESSING.value
        batch.started_at = utc_now()

    @staticmethod
    def mark_completed(batch: ImportBatch, imported_rows: int) -> None:
        batch.status = ImportStatus.COMPLETED.value
        batch.valid_rows = imported_rows
        batch.imported_rows = imported_rows
        batch.rejected_rows = 0
        batch.completed_at = utc_now()

    @staticmethod
    def mark_failed(batch: ImportBatch, error_code: str) -> None:
        batch.status = ImportStatus.FAILED.value
        batch.error_summary = {"code": error_code}
        batch.completed_at = utc_now()


class ProductCategoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_many(self, rows: list[ProductCategoryRow]) -> int:
        names = [row.category_name for row in rows]
        existing = {
            category.category_name: category
            for category in self.session.scalars(
                select(ProductCategory).where(
                    ProductCategory.category_name.in_(names)
                )
            )
        }
        for row in rows:
            category = existing.get(row.category_name)
            if category is None:
                self.session.add(
                    ProductCategory(
                        category_name=row.category_name,
                        category_name_english=row.category_name_english,
                    )
                )
            else:
                category.category_name_english = row.category_name_english
        return len(rows)


class AuditEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        actor_id: int,
        action: str,
        entity_id: int,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditEvent(
                actor_id=actor_id,
                action=action,
                entity_type="import_batch",
                entity_id=str(entity_id),
                payload_json=payload,
            )
        )
