from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models import User, UserRole
from app.modules.auth.dependencies import require_roles
from app.modules.datasets.schemas import (
    DatasetFingerprintResponse,
    DatasetSnapshotResponse,
)
from app.modules.datasets.service import DatasetFoundationService


router = APIRouter(prefix="/datasets", tags=["datasets"])
dataset_reader = require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.MANAGER)
dataset_builder = require_roles(UserRole.ADMIN, UserRole.ANALYST)


def get_service(session: Session = Depends(get_db)) -> DatasetFoundationService:
    return DatasetFoundationService(session)


@router.get("/fingerprint", response_model=DatasetFingerprintResponse)
def fingerprint(
    maturity_days: int = Query(default=30, ge=1, le=365),
    service: DatasetFoundationService = Depends(get_service),
    _user: User = Depends(dataset_reader),
) -> DatasetFingerprintResponse:
    return service.fingerprint(maturity_days)


@router.post("/daily-sales/rebuild", response_model=DatasetSnapshotResponse)
def rebuild_daily_sales(
    maturity_days: int = Query(default=30, ge=1, le=365),
    service: DatasetFoundationService = Depends(get_service),
    user: User = Depends(dataset_builder),
) -> DatasetSnapshotResponse:
    return service.rebuild_daily_sales(maturity_days, user)


@router.get("/snapshots/latest", response_model=DatasetSnapshotResponse)
def latest_snapshot(
    service: DatasetFoundationService = Depends(get_service),
    _user: User = Depends(dataset_reader),
) -> DatasetSnapshotResponse:
    return service.latest_snapshot()
