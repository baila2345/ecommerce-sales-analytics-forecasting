from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.db.models import User, UserRole
from app.modules.auth.dependencies import require_roles
from app.modules.imports.datasets import DATASETS, DATASETS_BY_SLUG, DatasetSpec
from app.modules.imports.factory import (
    build_dataset_import_services,
    build_product_category_import_services,
)
from app.modules.imports.schemas import (
    DatasetInfoResponse,
    DatasetPreviewResponse,
    ImportCommitResponse,
    ProductCategoryPreviewResponse,
)


router = APIRouter(prefix="/imports", tags=["data imports"])
import_user = require_roles(UserRole.ADMIN, UserRole.ANALYST)


@router.get("/datasets", response_model=list[DatasetInfoResponse])
def list_import_datasets(
    _user: User = Depends(import_user),
) -> list[DatasetInfoResponse]:
    product_categories = DatasetInfoResponse(
        dataset_type="product_categories",
        route_slug="product-categories",
        display_name="Danh mục sản phẩm",
        expected_filename="product_category_name_translation.csv",
        columns=[
            "product_category_name",
            "product_category_name_english",
        ],
        max_file_size_mb=5,
    )
    return [
        product_categories,
        *[
            DatasetInfoResponse(
                dataset_type=dataset.dataset_type,
                route_slug=dataset.route_slug,
                display_name=dataset.display_name,
                expected_filename=dataset.expected_filename,
                columns=list(dataset.columns),
                max_file_size_mb=dataset.max_file_size_mb,
            )
            for dataset in DATASETS
        ],
    ]


@router.post(
    "/product-categories/preview",
    response_model=ProductCategoryPreviewResponse,
)
async def preview_product_categories(
    file: UploadFile = File(...),
    user: User = Depends(import_user),
    session: Session = Depends(get_db),
) -> ProductCategoryPreviewResponse:
    outcome = await build_product_category_import_services(session).preview.execute(
        file,
        user,
    )
    return ProductCategoryPreviewResponse.from_outcome(outcome)


@router.post(
    "/product-categories/{batch_id}/commit",
    response_model=ImportCommitResponse,
)
async def import_product_categories(
    batch_id: int,
    file: UploadFile = File(...),
    user: User = Depends(import_user),
    session: Session = Depends(get_db),
) -> ImportCommitResponse:
    outcome = await build_product_category_import_services(session).commit.execute(
        batch_id,
        file,
        user,
    )
    return ImportCommitResponse.from_outcome(outcome)


def get_dataset(dataset_slug: str) -> DatasetSpec:
    dataset = DATASETS_BY_SLUG.get(dataset_slug)
    if dataset is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="IMPORT_DATASET_NOT_FOUND",
            message="Import dataset was not found",
        )
    return dataset


@router.post("/{dataset_slug}/preview", response_model=DatasetPreviewResponse)
async def preview_dataset(
    dataset_slug: str,
    file: UploadFile = File(...),
    user: User = Depends(import_user),
    session: Session = Depends(get_db),
) -> DatasetPreviewResponse:
    dataset = get_dataset(dataset_slug)
    outcome = await build_dataset_import_services(
        session,
        dataset,
    ).preview.execute(file, user)
    return DatasetPreviewResponse.from_outcome(outcome)


@router.post(
    "/{dataset_slug}/{batch_id}/commit",
    response_model=ImportCommitResponse,
)
async def commit_dataset(
    dataset_slug: str,
    batch_id: int,
    file: UploadFile = File(...),
    user: User = Depends(import_user),
    session: Session = Depends(get_db),
) -> ImportCommitResponse:
    dataset = get_dataset(dataset_slug)
    outcome = await build_dataset_import_services(
        session,
        dataset,
    ).commit.execute(batch_id, file, user)
    return ImportCommitResponse.from_outcome(outcome)
