import csv
import io
from collections.abc import Iterator
from typing import Any

from app.modules.imports.datasets import DatasetSpec
from app.modules.imports.domain import DatasetInspection, ValidationIssue
from app.modules.imports.exceptions import CsvParsingError


class DatasetCsvParser:
    def __init__(
        self,
        dataset: DatasetSpec,
        preview_row_limit: int = 5,
        max_stored_issues: int = 1000,
    ) -> None:
        self.dataset = dataset
        self.preview_row_limit = preview_row_limit
        self.max_stored_issues = max_stored_issues

    def inspect(self, content: bytes) -> DatasetInspection:
        reader = self._reader(content)
        columns = reader.fieldnames or []
        inspection = DatasetInspection(
            columns=columns,
            preview_rows=[],
            issues=[],
            rejected_row_numbers=set(),
            reference_rows={
                reference.field_name: {} for reference in self.dataset.references
            },
            total_rows=0,
        )
        if columns != list(self.dataset.columns):
            inspection.add_issue(
                ValidationIssue(
                    row_number=None,
                    field_name=None,
                    code="invalid_headers",
                    message="CSV columns must be: " + ", ".join(self.dataset.columns),
                ),
                self.max_stored_issues,
            )
            return inspection

        seen_keys: set[tuple[Any, ...]] = set()
        try:
            for row_number, raw_row in enumerate(reader, start=2):
                inspection.total_rows += 1
                parsed, issues = self._parse_row(row_number, raw_row)
                key = tuple(parsed.get(field) for field in self.dataset.key_fields)
                if not issues and self.dataset.key_fields:
                    if key in seen_keys:
                        issues.append(
                            ValidationIssue(
                                row_number=row_number,
                                field_name=", ".join(self.dataset.key_fields),
                                code="duplicate",
                                message=(
                                    "Primary key appears more than once in this file"
                                ),
                                raw_data=self._raw_data(raw_row),
                            )
                        )
                    else:
                        seen_keys.add(key)

                if issues:
                    for issue in issues:
                        inspection.add_issue(issue, self.max_stored_issues)
                    continue

                if len(inspection.preview_rows) < self.preview_row_limit:
                    inspection.preview_rows.append(parsed)
                for reference in self.dataset.references:
                    value = parsed.get(reference.field_name)
                    if value is not None:
                        inspection.reference_rows[reference.field_name].setdefault(
                            value,
                            row_number,
                        )
        except csv.Error as exc:
            raise CsvParsingError(
                code="CSV_FORMAT_INVALID",
                message="The CSV file is malformed",
            ) from exc

        if inspection.total_rows == 0:
            inspection.add_issue(
                ValidationIssue(None, None, "no_data", "CSV file has no data rows"),
                self.max_stored_issues,
            )
        return inspection

    def iter_rows(self, content: bytes) -> Iterator[dict[str, Any]]:
        reader = self._reader(content)
        if (reader.fieldnames or []) != list(self.dataset.columns):
            raise CsvParsingError(
                code="CSV_HEADERS_CHANGED",
                message="CSV headers changed after preview",
            )
        try:
            for row_number, raw_row in enumerate(reader, start=2):
                parsed, issues = self._parse_row(row_number, raw_row)
                if issues:
                    raise CsvParsingError(
                        code="CSV_DATA_CHANGED",
                        message="CSV data changed after preview",
                    )
                yield parsed
        except csv.Error as exc:
            raise CsvParsingError(
                code="CSV_FORMAT_INVALID",
                message="The CSV file is malformed",
            ) from exc

    def _reader(self, content: bytes) -> csv.DictReader:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CsvParsingError(
                code="CSV_ENCODING_INVALID",
                message="The CSV file must use UTF-8 encoding",
            ) from exc
        return csv.DictReader(io.StringIO(text, newline=""), strict=True)

    def _parse_row(
        self,
        row_number: int,
        raw_row: dict[str | None, str | list[str] | None],
    ) -> tuple[dict[str, Any], list[ValidationIssue]]:
        parsed: dict[str, Any] = {}
        issues: list[ValidationIssue] = []
        raw_data = self._raw_data(raw_row)
        if None in raw_row:
            issues.append(
                ValidationIssue(
                    row_number,
                    None,
                    "unexpected_column",
                    "Row contains more values than the CSV header",
                    raw_data,
                )
            )

        for field in self.dataset.fields:
            value = raw_row.get(field.csv_name)
            normalized = value.strip() if isinstance(value, str) else ""
            if not normalized:
                parsed[field.name] = None
                if field.required:
                    issues.append(
                        ValidationIssue(
                            row_number,
                            field.name,
                            "required",
                            f"{field.name} is required",
                            raw_data,
                        )
                    )
                continue
            try:
                parsed[field.name] = field.converter(normalized)
            except ValueError as exc:
                issues.append(
                    ValidationIssue(
                        row_number,
                        field.name,
                        "invalid_value",
                        f"{field.name} {exc}",
                        raw_data,
                    )
                )

        if not issues and self.dataset.row_validator is not None:
            for field_name, message in self.dataset.row_validator(parsed).items():
                issues.append(
                    ValidationIssue(
                        row_number,
                        field_name,
                        "invalid_value",
                        f"{field_name} {message}",
                        raw_data,
                    )
                )
        return parsed, issues

    @staticmethod
    def _raw_data(
        raw_row: dict[str | None, str | list[str] | None],
    ) -> dict[str, Any]:
        return {
            str(key): value
            for key, value in raw_row.items()
            if key is not None
        }
