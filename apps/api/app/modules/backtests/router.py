from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.db.models import User, UserRole
from app.modules.auth.dependencies import require_roles
from app.modules.backtests.schemas import BacktestRequest, BacktestRunResponse
from app.modules.backtests.service import BacktestService


router = APIRouter(prefix="/models", tags=["model backtests"])
backtest_runner = require_roles(UserRole.ADMIN, UserRole.ANALYST)
backtest_reader = require_roles(UserRole.ADMIN, UserRole.ANALYST, UserRole.MANAGER)


def get_service(session: Session = Depends(get_db)) -> BacktestService:
    return BacktestService(session)


@router.post("/backtests", response_model=BacktestRunResponse)
def run_backtest(
    request: BacktestRequest,
    service: BacktestService = Depends(get_service),
    user: User = Depends(backtest_runner),
) -> BacktestRunResponse:
    return service.run(request, user)


@router.get("/runs/latest", response_model=BacktestRunResponse)
def get_latest_model_run(
    service: BacktestService = Depends(get_service),
    _user: User = Depends(backtest_reader),
) -> BacktestRunResponse:
    return service.latest_run("M0")


@router.get("/runs/{run_id}", response_model=BacktestRunResponse)
def get_model_run(
    run_id: int,
    service: BacktestService = Depends(get_service),
    _user: User = Depends(backtest_reader),
) -> BacktestRunResponse:
    return service.get_run(run_id)
