from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models import User, UserRole
from app.modules.auth.dependencies import require_roles
from app.modules.data_quality.repository import DataQualityRepository
from app.modules.data_quality.schemas import DataQualityReportResponse
from app.modules.data_quality.service import DataQualityService


router = APIRouter(prefix="/datasets", tags=["data-quality"])
quality_user = require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.MANAGER)


def get_service(session: Session = Depends(get_db)) -> DataQualityService:
    return DataQualityService(DataQualityRepository(session))


@router.get("/quality", response_model=DataQualityReportResponse)
def quality_report(
    service: DataQualityService = Depends(get_service),
    _user: User = Depends(quality_user),
) -> DataQualityReportResponse:
    return service.report()
