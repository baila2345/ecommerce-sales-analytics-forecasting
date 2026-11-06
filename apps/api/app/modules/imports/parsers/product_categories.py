import csv
import io

from app.modules.imports.domain import (
    ParsedProductCategories,
    ProductCategoryRow,
    ValidationIssue,
)
from app.modules.imports.exceptions import CsvParsingError


class ProductCategoryCsvParser:
    expected_columns = (
        "product_category_name",
        "product_category_name_english",
    )

    def __init__(self, preview_row_limit: int = 5) -> None:
        self.preview_row_limit = preview_row_limit

    def parse(self, content: bytes) -> ParsedProductCategories:
        text = self._decode(content)
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            columns = reader.fieldnames or []
            if columns != list(self.expected_columns):
                return self._invalid_headers(columns)
            return self._parse_rows(reader, columns)
        except csv.Error as exc:
            raise CsvParsingError(
                code="CSV_FORMAT_INVALID",
                message="The CSV file is malformed",
            ) from exc

    @staticmethod
    def _decode(content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvParsingError(
                code="CSV_ENCODING_INVALID",
                message="The CSV file must use UTF-8 encoding",
            ) from exc

    def _parse_rows(
        self,
        reader: csv.DictReader,
        columns: list[str],
    ) -> ParsedProductCategories:
        rows: list[ProductCategoryRow] = []
        preview_rows: list[ProductCategoryRow] = []
        issues: list[ValidationIssue] = []
        rejected_rows: set[int] = set()
        seen_categories: set[str] = set()
        total_rows = 0

        for row_number, raw_row in enumerate(reader, start=2):
            total_rows += 1
            category_name = (raw_row.get(self.expected_columns[0]) or "").strip()
            english_name = (raw_row.get(self.expected_columns[1]) or "").strip()
            row_issues = self._validate_row(
                row_number,
                raw_row,
                category_name,
                english_name,
                seen_categories,
            )
            if category_name:
                seen_categories.add(category_name)
            if row_issues:
                issues.extend(row_issues)
                rejected_rows.add(row_number)
                continue

            row = ProductCategoryRow(category_name, english_name)
            rows.append(row)
            if len(preview_rows) < self.preview_row_limit:
                preview_rows.append(row)

        if total_rows == 0:
            issues.append(
                self._issue(None, None, "no_data", "CSV file has no data rows")
            )

        return ParsedProductCategories(
            columns=columns,
            rows=rows,
            preview_rows=preview_rows,
            issues=issues,
            rejected_row_numbers=rejected_rows,
            total_rows=total_rows,
        )

    def _validate_row(
        self,
        row_number: int,
        raw_row: dict[str | None, str | list[str] | None],
        category_name: str,
        english_name: str,
        seen_categories: set[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if None in raw_row:
            issues.append(
                self._issue(
                    row_number,
                    None,
                    "unexpected_column",
                    "Row contains more values than the CSV header",
                )
            )
        issues.extend(
            self._validate_value(
                row_number,
                self.expected_columns[0],
                category_name,
                "Product category name",
            )
        )
        if category_name and category_name in seen_categories:
            issues.append(
                self._issue(
                    row_number,
                    self.expected_columns[0],
                    "duplicate",
                    "Product category appears more than once in this file",
                )
            )
        issues.extend(
            self._validate_value(
                row_number,
                self.expected_columns[1],
                english_name,
                "English category name",
            )
        )
        return issues

    def _validate_value(
        self,
        row_number: int,
        field_name: str,
        value: str,
        label: str,
    ) -> list[ValidationIssue]:
        if not value:
            return [
                self._issue(
                    row_number,
                    field_name,
                    "required",
                    f"{label} is required",
                )
            ]
        if len(value) > 255:
            return [
                self._issue(
                    row_number,
                    field_name,
                    "too_long",
                    f"{label} must not exceed 255 characters",
                )
            ]
        return []

    def _invalid_headers(self, columns: list[str]) -> ParsedProductCategories:
        return ParsedProductCategories(
            columns=columns,
            rows=[],
            preview_rows=[],
            issues=[
                self._issue(
                    None,
                    None,
                    "invalid_headers",
                    "CSV columns must be: " + ", ".join(self.expected_columns),
                )
            ],
            rejected_row_numbers=set(),
            total_rows=0,
        )

    @staticmethod
    def _issue(
        row_number: int | None,
        field_name: str | None,
        code: str,
        message: str,
    ) -> ValidationIssue:
        return ValidationIssue(row_number, field_name, code, message)
