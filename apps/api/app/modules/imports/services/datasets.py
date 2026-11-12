from fastapi import UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utc_now
from app.db.models import ImportBatch, ImportStatus, User
from app.modules.analytics.cache import AnalyticsCache
from app.modules.imports.datasets import DatasetSpec
from app.modules.imports.domain import (
    DatasetInspection,
    DatasetPreviewOutcome,
    ImportCommitOutcome,
    ValidationIssue,
)
from app.modules.imports.exceptions import CsvParsingError
from app.modules.imports.file_reader import CsvUploadReader
from app.modules.imports.parsers.generic import DatasetCsvParser
from app.modules.imports.repositories import (
    AuditEventRepository,
    DatasetRepository,
    ImportBatchRepository,
)
from app.modules.datasets.repository import DatasetFoundationRepository


class PreviewDatasetService:
    def __init__(
        self,
        session: Session,
        dataset: DatasetSpec,
        file_reader: CsvUploadReader,
        parser: DatasetCsvParser,
        batches: ImportBatchRepository,
        data: DatasetRepository,
        audit_events: AuditEventRepository,
    ) -> None:
        self.session = session
        self.dataset = dataset
        self.file_reader = file_reader
        self.parser = parser
        self.batches = batches
        self.data = data
        self.audit_events = audit_events

    async def execute(
        self,
        upload: UploadFile,
        user: User,
    ) -> DatasetPreviewOutcome:
        uploaded_csv = await self.file_reader.read(upload)
        inspection = self._inspect(uploaded_csv.content)
        self._validate_references(inspection)
        has_issues = not inspection.can_import
        batch = self.batches.create(
            dataset_type=self.dataset.dataset_type,
            filename=uploaded_csv.filename,
            checksum_sha256=uploaded_csv.checksum_sha256,
            user_id=user.id,
            total_rows=inspection.total_rows,
            valid_rows=inspection.valid_rows,
            rejected_rows=len(inspection.rejected_row_numbers),
            status=(
                ImportStatus.FAILED.value
                if has_issues
                else ImportStatus.PENDING.value
            ),
            error_summary=(
                {
                    "validation_error_count": inspection.issue_count,
                    "stored_error_count": len(inspection.issues),
                }
                if has_issues
                else None
            ),
            completed_at=utc_now() if has_issues else None,
        )
        self.batches.add_validation_issues(batch.id, inspection.issues)
        self.audit_events.record(
            actor_id=user.id,
            action="data_import.previewed",
            entity_id=batch.id,
            payload={
                "dataset_type": self.dataset.dataset_type,
                "filename": uploaded_csv.filename,
                "can_import": inspection.can_import,
            },
        )
        self.session.commit()
        return DatasetPreviewOutcome(
            batch_id=batch.id,
            dataset_type=self.dataset.dataset_type,
            filename=uploaded_csv.filename,
            inspection=inspection,
        )

    def _inspect(self, content: bytes) -> DatasetInspection:
        try:
            return self.parser.inspect(content)
        except CsvParsingError as exc:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code=exc.code,
                message=exc.message,
            ) from exc

    def _validate_references(self, inspection: DatasetInspection) -> None:
        if not inspection.can_import:
            return
        for reference in self.dataset.references:
            value_rows = inspection.reference_rows[reference.field_name]
            missing_values = self.data.find_missing_references(
                reference,
                set(value_rows),
            )
            for value in missing_values:
                inspection.add_issue(
                    ValidationIssue(
                        row_number=value_rows[value],
                        field_name=reference.field_name,
                        code="reference_not_found",
                        message=(
                            f"{reference.field_name} does not exist in "
                            f"{reference.model.__tablename__}"
                        ),
                        raw_data={reference.field_name: value},
                    )
                )


class CommitDatasetService:
    def __init__(
        self,
        session: Session,
        dataset: DatasetSpec,
        file_reader: CsvUploadReader,
        parser: DatasetCsvParser,
        batches: ImportBatchRepository,
        data: DatasetRepository,
        audit_events: AuditEventRepository,
        analytics_cache: AnalyticsCache | None = None,
    ) -> None:
        self.session = session
        self.dataset = dataset
        self.file_reader = file_reader
        self.parser = parser
        self.batches = batches
        self.data = data
        self.audit_events = audit_events
        self.analytics_cache = analytics_cache

    async def execute(
        self,
        batch_id: int,
        upload: UploadFile,
        user: User,
    ) -> ImportCommitOutcome:
        batch = self.batches.get_for_update(batch_id)
        self._authorize_batch(batch, user)
        assert batch is not None

        uploaded_csv = await self.file_reader.read(upload)
        if uploaded_csv.checksum_sha256 != batch.file_checksum_sha256:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IMPORT_FILE_CHANGED",
                message="The selected file is different from the previewed file",
            )

        self.batches.mark_processing(batch)
        try:
            imported_rows = self.data.import_rows(
                self.dataset,
                self.parser.iter_rows(uploaded_csv.content),
            )
            self.batches.mark_completed(batch, imported_rows)
            self.audit_events.record(
                actor_id=user.id,
                action="data_import.completed",
                entity_id=batch.id,
                payload={
                    "dataset_type": self.dataset.dataset_type,
                    "imported_rows": imported_rows,
                },
            )
            DatasetFoundationRepository(
                self.session
            ).mark_ready_snapshots_stale()
            self.session.commit()
            if self.analytics_cache is not None:
                self.analytics_cache.invalidate_dashboards()
        except CsvParsingError as exc:
            self.session.rollback()
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code=exc.code,
                message=exc.message,
            ) from exc
        except SQLAlchemyError as exc:
            self._record_database_failure(batch_id)
            raise AppError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="IMPORT_FAILED",
                message="The file could not be imported",
            ) from exc

        return ImportCommitOutcome(
            batch_id=batch.id,
            dataset_type=self.dataset.dataset_type,
            status=batch.status,
            imported_rows=batch.imported_rows,
        )

    def _authorize_batch(self, batch: ImportBatch | None, user: User) -> None:
        if batch is None or batch.dataset_type != self.dataset.dataset_type:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="IMPORT_BATCH_NOT_FOUND",
                message="Import batch was not found",
            )
        if batch.uploaded_by_id != user.id:
            raise AppError(
                status_code=status.HTTP_403_FORBIDDEN,
                code="IMPORT_BATCH_FORBIDDEN",
                message="Only the user who previewed this file can import it",
            )
        if batch.status != ImportStatus.PENDING.value:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IMPORT_BATCH_NOT_PENDING",
                message="This import batch is no longer awaiting confirmation",
            )

    def _record_database_failure(self, batch_id: int) -> None:
        self.session.rollback()
        failed_batch = self.batches.get(batch_id)
        if failed_batch is not None:
            self.batches.mark_failed(failed_batch, "database_error")
            self.session.commit()
