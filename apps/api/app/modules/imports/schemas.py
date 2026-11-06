from typing import Any

from pydantic import BaseModel, Field

from app.modules.imports.domain import (
    ImportCommitOutcome,
    DatasetPreviewOutcome,
    ProductCategoryPreviewOutcome,
)


class ProductCategoryPreviewRow(BaseModel):
    product_category_name: str
    product_category_name_english: str


class ImportValidationErrorResponse(BaseModel):
    row_number: int | None = None
    field_name: str | None = None
    code: str
    message: str


class ProductCategoryPreviewResponse(BaseModel):
    batch_id: int
    dataset_type: str
    filename: str
    columns: list[str]
    total_rows: int
    valid_rows: int
    rejected_rows: int
    preview_rows: list[ProductCategoryPreviewRow]
    errors: list[ImportValidationErrorResponse]
    can_import: bool

    @classmethod
    def from_outcome(
        cls,
        outcome: ProductCategoryPreviewOutcome,
    ) -> "ProductCategoryPreviewResponse":
        parsed = outcome.parsed
        return cls(
            batch_id=outcome.batch_id,
            dataset_type="product_categories",
            filename=outcome.filename,
            columns=parsed.columns,
            total_rows=parsed.total_rows,
            valid_rows=parsed.valid_rows,
            rejected_rows=len(parsed.rejected_row_numbers),
            preview_rows=[
                ProductCategoryPreviewRow(
                    product_category_name=row.category_name,
                    product_category_name_english=row.category_name_english,
                )
                for row in parsed.preview_rows
            ],
            errors=[
                ImportValidationErrorResponse(
                    row_number=issue.row_number,
                    field_name=issue.field_name,
                    code=issue.code,
                    message=issue.message,
                )
                for issue in parsed.issues[:100]
            ],
            can_import=parsed.can_import,
        )


class ImportCommitResponse(BaseModel):
    batch_id: int
    dataset_type: str
    status: str
    imported_rows: int = Field(ge=0)

    @classmethod
    def from_outcome(cls, outcome: ImportCommitOutcome) -> "ImportCommitResponse":
        return cls(
            batch_id=outcome.batch_id,
            dataset_type=outcome.dataset_type,
            status=outcome.status,
            imported_rows=outcome.imported_rows,
        )


class DatasetInfoResponse(BaseModel):
    dataset_type: str
    route_slug: str
    display_name: str
    expected_filename: str
    columns: list[str]
    max_file_size_mb: int


class DatasetPreviewResponse(BaseModel):
    batch_id: int
    dataset_type: str
    filename: str
    columns: list[str]
    total_rows: int
    valid_rows: int
    rejected_rows: int
    preview_rows: list[dict[str, Any]]
    errors: list[ImportValidationErrorResponse]
    can_import: bool

    @classmethod
    def from_outcome(cls, outcome: DatasetPreviewOutcome) -> "DatasetPreviewResponse":
        inspection = outcome.inspection
        return cls(
            batch_id=outcome.batch_id,
            dataset_type=outcome.dataset_type,
            filename=outcome.filename,
            columns=inspection.columns,
            total_rows=inspection.total_rows,
            valid_rows=inspection.valid_rows,
            rejected_rows=len(inspection.rejected_row_numbers),
            preview_rows=inspection.preview_rows,
            errors=[
                ImportValidationErrorResponse(
                    row_number=issue.row_number,
                    field_name=issue.field_name,
                    code=issue.code,
                    message=issue.message,
                )
                for issue in inspection.issues[:100]
            ],
            can_import=inspection.can_import,
        )
