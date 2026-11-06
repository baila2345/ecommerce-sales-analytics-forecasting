from fastapi import UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.base import utc_now
from app.db.models import ImportBatch, ImportStatus, User
from app.modules.imports.domain import (
    ImportCommitOutcome,
    ParsedProductCategories,
    ProductCategoryPreviewOutcome,
)
from app.modules.imports.exceptions import CsvParsingError
from app.modules.imports.file_reader import CsvUploadReader
from app.modules.imports.parsers.product_categories import ProductCategoryCsvParser
from app.modules.imports.repositories import (
    AuditEventRepository,
    ImportBatchRepository,
    ProductCategoryRepository,
)


DATASET_TYPE = "product_categories"


class PreviewProductCategoriesService:
    def __init__(
        self,
        session: Session,
        file_reader: CsvUploadReader,
        parser: ProductCategoryCsvParser,
        batches: ImportBatchRepository,
        audit_events: AuditEventRepository,
    ) -> None:
        self.session = session
        self.file_reader = file_reader
        self.parser = parser
        self.batches = batches
        self.audit_events = audit_events

    async def execute(
        self,
        upload: UploadFile,
        user: User,
    ) -> ProductCategoryPreviewOutcome:
        uploaded_csv = await self.file_reader.read(upload)
        parsed = _parse(self.parser, uploaded_csv.content)
        has_issues = bool(parsed.issues)
        batch = self.batches.create(
            dataset_type=DATASET_TYPE,
            filename=uploaded_csv.filename,
            checksum_sha256=uploaded_csv.checksum_sha256,
            user_id=user.id,
            total_rows=parsed.total_rows,
            valid_rows=parsed.valid_rows,
            rejected_rows=len(parsed.rejected_row_numbers),
            status=(
                ImportStatus.FAILED.value
                if has_issues
                else ImportStatus.PENDING.value
            ),
            error_summary=(
                {"validation_error_count": len(parsed.issues)}
                if has_issues
                else None
            ),
            completed_at=utc_now() if has_issues else None,
        )
        self.batches.add_validation_issues(batch.id, parsed.issues)
        self.audit_events.record(
            actor_id=user.id,
            action="data_import.previewed",
            entity_id=batch.id,
            payload={
                "dataset_type": DATASET_TYPE,
                "filename": uploaded_csv.filename,
                "can_import": parsed.can_import,
            },
        )
        self.session.commit()
        return ProductCategoryPreviewOutcome(
            batch_id=batch.id,
            filename=uploaded_csv.filename,
            parsed=parsed,
        )


class CommitProductCategoriesService:
    def __init__(
        self,
        session: Session,
        file_reader: CsvUploadReader,
        parser: ProductCategoryCsvParser,
        batches: ImportBatchRepository,
        categories: ProductCategoryRepository,
        audit_events: AuditEventRepository,
    ) -> None:
        self.session = session
        self.file_reader = file_reader
        self.parser = parser
        self.batches = batches
        self.categories = categories
        self.audit_events = audit_events

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
        parsed = _parse(self.parser, uploaded_csv.content)
        self._verify_file(batch, uploaded_csv.checksum_sha256, parsed.can_import)

        self.batches.mark_processing(batch)
        try:
            imported_rows = self.categories.upsert_many(parsed.rows)
            self.batches.mark_completed(batch, imported_rows)
            self.audit_events.record(
                actor_id=user.id,
                action="data_import.completed",
                entity_id=batch.id,
                payload={
                    "dataset_type": DATASET_TYPE,
                    "imported_rows": imported_rows,
                },
            )
            self.session.commit()
        except SQLAlchemyError as exc:
            self._record_database_failure(batch_id)
            raise AppError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="IMPORT_FAILED",
                message="The file could not be imported",
            ) from exc

        return ImportCommitOutcome(
            batch_id=batch.id,
            dataset_type=DATASET_TYPE,
            status=batch.status,
            imported_rows=batch.imported_rows,
        )

    @staticmethod
    def _authorize_batch(batch: ImportBatch | None, user: User) -> None:
        if batch is None or batch.dataset_type != DATASET_TYPE:
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

    @staticmethod
    def _verify_file(
        batch: ImportBatch,
        checksum_sha256: str,
        can_import: bool,
    ) -> None:
        if checksum_sha256 != batch.file_checksum_sha256:
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                code="IMPORT_FILE_CHANGED",
                message="The selected file is different from the previewed file",
            )
        if not can_import:
            raise AppError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="IMPORT_FILE_INVALID",
                message="The CSV file is no longer valid",
            )

    def _record_database_failure(self, batch_id: int) -> None:
        self.session.rollback()
        failed_batch = self.batches.get(batch_id)
        if failed_batch is not None:
            self.batches.mark_failed(failed_batch, "database_error")
            self.session.commit()


def _parse(
    parser: ProductCategoryCsvParser,
    content: bytes,
) -> ParsedProductCategories:
    try:
        return parser.parse(content)
    except CsvParsingError as exc:
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=exc.code,
            message=exc.message,
        ) from exc
