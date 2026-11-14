from typing import Literal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models import User, UserRole
from app.modules.auth.dependencies import require_roles
from app.modules.backtests.schemas import BacktestRequest, BacktestRunResponse
from app.modules.backtests.queue import (
    BacktestDispatcher,
    get_backtest_dispatcher,
)
from app.modules.backtests.service import BacktestService


router = APIRouter(prefix="/models", tags=["model backtests"])
backtest_runner = require_roles(UserRole.ADMIN, UserRole.ANALYST)
backtest_reader = require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.MANAGER)


def get_service(
    session: Session = Depends(get_db),
    dispatcher: BacktestDispatcher = Depends(get_backtest_dispatcher),
) -> BacktestService:
    return BacktestService(session, dispatcher)


@router.post(
    "/backtests",
    response_model=BacktestRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_backtest(
    request: BacktestRequest,
    service: BacktestService = Depends(get_service),
    user: User = Depends(backtest_runner),
) -> BacktestRunResponse:
    return service.enqueue(request, user)


@router.get("/runs/latest", response_model=BacktestRunResponse)
def get_latest_model_run(
    model_code: Literal["M0", "M1"] = "M0",
    service: BacktestService = Depends(get_service),
    _user: User = Depends(backtest_reader),
) -> BacktestRunResponse:
    return service.latest_run(model_code)


@router.get("/runs/{run_id}", response_model=BacktestRunResponse)
def get_model_run(
    run_id: int,
    service: BacktestService = Depends(get_service),
    _user: User = Depends(backtest_reader),
) -> BacktestRunResponse:
    return service.get_run(run_id)
