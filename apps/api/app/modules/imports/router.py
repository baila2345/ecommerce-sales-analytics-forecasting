from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models import User, UserRole
from app.modules.auth.dependencies import require_roles
from app.modules.imports.factory import build_product_category_import_services
from app.modules.imports.schemas import (
    ImportCommitResponse,
    ProductCategoryPreviewResponse,
)


router = APIRouter(prefix="/imports", tags=["data imports"])
import_user = require_roles(UserRole.ADMIN, UserRole.ANALYST)


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
