from dataclasses import dataclass


@dataclass(frozen=True)
class UploadedCsv:
    filename: str
    content: bytes
    checksum_sha256: str


@dataclass(frozen=True)
class ValidationIssue:
    row_number: int | None
    field_name: str | None
    code: str
    message: str


@dataclass(frozen=True)
class ProductCategoryRow:
    category_name: str
    category_name_english: str


@dataclass(frozen=True)
class ParsedProductCategories:
    columns: list[str]
    rows: list[ProductCategoryRow]
    preview_rows: list[ProductCategoryRow]
    issues: list[ValidationIssue]
    rejected_row_numbers: set[int]
    total_rows: int

    @property
    def valid_rows(self) -> int:
        return self.total_rows - len(self.rejected_row_numbers)

    @property
    def can_import(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class ProductCategoryPreviewOutcome:
    batch_id: int
    filename: str
    parsed: ParsedProductCategories


@dataclass(frozen=True)
class ImportCommitOutcome:
    batch_id: int
    dataset_type: str
    status: str
    imported_rows: int
