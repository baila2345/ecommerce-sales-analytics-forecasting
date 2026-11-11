from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.db.models import User, UserRole
from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.schemas import (
    AnalyticsDashboardResponse,
    AnalyticsQuery,
    FilterOptions,
)
from app.modules.analytics.service import AnalyticsService
from app.modules.auth.dependencies import require_roles


router = APIRouter(prefix="/analytics", tags=["analytics"])
analytics_user = require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.MANAGER)
analytics_cache = AnalyticsCache(get_settings().redis_url)


def get_service(session: Session = Depends(get_db)) -> AnalyticsService:
    cache = analytics_cache if session.get_bind().dialect.name == "mysql" else None
    return AnalyticsService(AnalyticsRepository(session), cache)


def get_query(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    state: str | None = Query(default=None, min_length=2, max_length=2),
    category: str | None = Query(default=None, max_length=255),
    seller_id: str | None = Query(default=None, max_length=32),
) -> AnalyticsQuery:
    if date_from and date_to and date_from > date_to:
        raise AppError(
            status_code=422,
            code="INVALID_DATE_RANGE",
            message="date_from must be before or equal to date_to",
        )
    return AnalyticsQuery(
        date_from=date_from,
        date_to=date_to,
        state=state,
        category=category,
        seller_id=seller_id,
    )


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
def dashboard(
    query: AnalyticsQuery = Depends(get_query),
    service: AnalyticsService = Depends(get_service),
    _user: User = Depends(analytics_user),
) -> AnalyticsDashboardResponse:
    return service.dashboard(query)


@router.get("/filters", response_model=FilterOptions)
def filters(
    service: AnalyticsService = Depends(get_service),
    _user: User = Depends(analytics_user),
) -> FilterOptions:
    return service.filter_options()


@router.get("/export")
def export_report(
    query: AnalyticsQuery = Depends(get_query),
    service: AnalyticsService = Depends(get_service),
    _user: User = Depends(analytics_user),
) -> Response:
    return Response(
        content=service.export_csv(query),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=salescope-analytics.csv"
        },
    )
