from dataclasses import dataclass, field
from typing import Any


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
    raw_data: dict[str, Any] | None = None


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


@dataclass
class DatasetInspection:
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    issues: list[ValidationIssue]
    rejected_row_numbers: set[int]
    reference_rows: dict[str, dict[Any, int]]
    total_rows: int
    issue_count: int = 0

    @property
    def valid_rows(self) -> int:
        return self.total_rows - len(self.rejected_row_numbers)

    @property
    def can_import(self) -> bool:
        return self.issue_count == 0

    def add_issue(self, issue: ValidationIssue, max_stored: int = 1000) -> None:
        self.issue_count += 1
        if issue.row_number is not None:
            self.rejected_row_numbers.add(issue.row_number)
        if len(self.issues) < max_stored:
            self.issues.append(issue)


@dataclass(frozen=True)
class DatasetPreviewOutcome:
    batch_id: int
    dataset_type: str
    filename: str
    inspection: DatasetInspection
