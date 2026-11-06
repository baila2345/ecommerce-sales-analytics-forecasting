import pytest

from app.modules.imports.exceptions import CsvParsingError
from app.modules.imports.parsers.product_categories import ProductCategoryCsvParser


def test_parser_accepts_utf8_bom_and_limits_preview_rows() -> None:
    content = (
        "\ufeffproduct_category_name,product_category_name_english\n"
        "category_1,category_one\n"
        "category_2,category_two\n"
        "category_3,category_three\n"
    ).encode()

    result = ProductCategoryCsvParser(preview_row_limit=2).parse(content)

    assert result.can_import is True
    assert result.total_rows == 3
    assert len(result.rows) == 3
    assert len(result.preview_rows) == 2


def test_parser_reports_required_and_duplicate_values() -> None:
    content = (
        b"product_category_name,product_category_name_english\n"
        b"beleza_saude,health_beauty\n"
        b"beleza_saude,beauty\n"
        b"missing_translation,\n"
    )

    result = ProductCategoryCsvParser().parse(content)

    assert result.can_import is False
    assert result.valid_rows == 1
    assert result.rejected_row_numbers == {3, 4}
    assert {issue.code for issue in result.issues} == {"duplicate", "required"}


def test_parser_rejects_non_utf8_content() -> None:
    with pytest.raises(CsvParsingError) as error:
        ProductCategoryCsvParser().parse(b"\xff\xfe\x00")

    assert error.value.code == "CSV_ENCODING_INVALID"
