from datetime import datetime
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import (
    AuditEvent,
    ImportBatch,
    ImportError,
    ImportStatus,
    ProductCategory,
)
from app.modules.imports.datasets import DatasetSpec, ReferenceSpec
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
                    raw_data=issue.raw_data,
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


class DatasetRepository:
    def __init__(self, session: Session, chunk_size: int = 1000) -> None:
        self.session = session
        self.chunk_size = chunk_size

    def find_missing_references(
        self,
        reference: ReferenceSpec,
        values: set[Any],
    ) -> set[Any]:
        if not values:
            return set()
        column = getattr(reference.model, reference.target_field)
        existing: set[Any] = set()
        value_list = list(values)
        for start in range(0, len(value_list), self.chunk_size):
            chunk = value_list[start : start + self.chunk_size]
            existing.update(
                self.session.scalars(select(column).where(column.in_(chunk)))
            )
        return values - existing

    def import_rows(
        self,
        dataset: DatasetSpec,
        rows: Iterable[dict[str, Any]],
    ) -> int:
        if dataset.replace_existing:
            self.session.execute(delete(dataset.model))

        imported_rows = 0
        chunk: list[dict[str, Any]] = []
        for row in rows:
            chunk.append(row)
            if len(chunk) >= self.chunk_size:
                self._write_chunk(dataset, chunk)
                imported_rows += len(chunk)
                chunk = []
        if chunk:
            self._write_chunk(dataset, chunk)
            imported_rows += len(chunk)
        return imported_rows

    def _write_chunk(
        self,
        dataset: DatasetSpec,
        rows: list[dict[str, Any]],
    ) -> None:
        if dataset.create_missing_categories:
            self._ensure_product_categories(rows)
        if dataset.replace_existing:
            self.session.execute(dataset.model.__table__.insert(), rows)
            return

        dialect_name = self.session.get_bind().dialect.name
        if dialect_name == "mysql":
            statement = mysql_insert(dataset.model).values(rows)
            statement = statement.on_duplicate_key_update(
                **{
                    field: statement.inserted[field]
                    for field in dataset.update_fields
                }
            )
        elif dialect_name == "sqlite":
            statement = sqlite_insert(dataset.model).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=list(dataset.key_fields),
                set_={
                    field: statement.excluded[field]
                    for field in dataset.update_fields
                },
            )
        else:
            raise RuntimeError(f"Unsupported database dialect: {dialect_name}")
        self.session.execute(statement)

    def _ensure_product_categories(self, rows: list[dict[str, Any]]) -> None:
        category_names = {
            row["product_category_name"]
            for row in rows
            if row.get("product_category_name")
        }
        if not category_names:
            return
        existing = set(
            self.session.scalars(
                select(ProductCategory.category_name).where(
                    ProductCategory.category_name.in_(category_names)
                )
            )
        )
        self.session.add_all(
            ProductCategory(category_name=name, category_name_english=None)
            for name in category_names - existing
        )
        self.session.flush()
