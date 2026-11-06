from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.imports.file_reader import CsvUploadReader
from app.modules.imports.datasets import DatasetSpec
from app.modules.imports.parsers.generic import DatasetCsvParser
from app.modules.imports.parsers.product_categories import ProductCategoryCsvParser
from app.modules.imports.repositories import (
    AuditEventRepository,
    ImportBatchRepository,
    ProductCategoryRepository,
    DatasetRepository,
)
from app.modules.imports.services.datasets import (
    CommitDatasetService,
    PreviewDatasetService,
)
from app.modules.imports.services.product_categories import (
    CommitProductCategoriesService,
    PreviewProductCategoriesService,
)


PRODUCT_CATEGORY_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class ProductCategoryImportServices:
    preview: PreviewProductCategoriesService
    commit: CommitProductCategoriesService


@dataclass(frozen=True)
class DatasetImportServices:
    preview: PreviewDatasetService
    commit: CommitDatasetService


def build_product_category_import_services(
    session: Session,
) -> ProductCategoryImportServices:
    file_reader = CsvUploadReader(PRODUCT_CATEGORY_MAX_FILE_SIZE_BYTES)
    parser = ProductCategoryCsvParser(preview_row_limit=5)
    batches = ImportBatchRepository(session)
    audit_events = AuditEventRepository(session)

    return ProductCategoryImportServices(
        preview=PreviewProductCategoriesService(
            session=session,
            file_reader=file_reader,
            parser=parser,
            batches=batches,
            audit_events=audit_events,
        ),
        commit=CommitProductCategoriesService(
            session=session,
            file_reader=file_reader,
            parser=parser,
            batches=batches,
            categories=ProductCategoryRepository(session),
            audit_events=audit_events,
        ),
    )


def build_dataset_import_services(
    session: Session,
    dataset: DatasetSpec,
) -> DatasetImportServices:
    file_reader = CsvUploadReader(dataset.max_file_size_mb * 1024 * 1024)
    parser = DatasetCsvParser(dataset, preview_row_limit=5)
    batches = ImportBatchRepository(session)
    data = DatasetRepository(session)
    audit_events = AuditEventRepository(session)
    return DatasetImportServices(
        preview=PreviewDatasetService(
            session,
            dataset,
            file_reader,
            parser,
            batches,
            data,
            audit_events,
        ),
        commit=CommitDatasetService(
            session,
            dataset,
            file_reader,
            parser,
            batches,
            data,
            audit_events,
        ),
    )
