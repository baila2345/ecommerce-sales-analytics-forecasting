from math import isfinite
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
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
    model_code: Literal["M0", "M1", "M2", "M3", "M4"] = "M0",
    dataset_fingerprint: str | None = Query(
        default=None, min_length=64, max_length=64
    ),
    horizon_days: int | None = None,
    holdout_days: int | None = Query(default=None, ge=30, le=180),
    min_train_days: int | None = Query(default=None, ge=90, le=730),
    step_days: int | None = Query(default=None, ge=7, le=90),
    season_length: int | None = Query(default=None, ge=2, le=30),
    sarima_maxiter: int | None = Query(default=None, ge=10, le=500),
    m2_n_estimators: int | None = Query(default=None, ge=50, le=1000),
    m2_learning_rate: float | None = Query(default=None, gt=0, le=0.3),
    m2_num_leaves: int | None = Query(default=None, ge=4, le=128),
    m2_max_depth: int | None = Query(default=None, ge=2, le=12),
    m2_min_child_samples: int | None = Query(default=None, ge=5, le=200),
    m2_seed: int | None = Query(default=None, ge=0, le=2_147_483_647),
    m3_n_estimators: int | None = Query(default=None, ge=50, le=1000),
    m3_learning_rate: float | None = Query(default=None, gt=0, le=0.3),
    m3_num_leaves: int | None = Query(default=None, ge=4, le=128),
    m3_max_depth: int | None = Query(default=None, ge=2, le=12),
    m3_min_child_samples: int | None = Query(default=None, ge=5, le=200),
    m3_seed: int | None = Query(default=None, ge=0, le=2_147_483_647),
    m4_alpha_grid: list[float] | None = Query(default=None, min_length=2),
    service: BacktestService = Depends(get_service),
    _user: User = Depends(backtest_reader),
) -> BacktestRunResponse:
    if horizon_days is not None and horizon_days not in (7, 30):
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_BACKTEST_HORIZON",
            message="Backtest horizon must be 7 or 30 days",
        )
    if m4_alpha_grid is not None and (
        len(m4_alpha_grid) > 21
        or len(set(m4_alpha_grid)) != len(m4_alpha_grid)
        or any(
            not isfinite(alpha) or alpha < 0 or alpha > 1
            for alpha in m4_alpha_grid
        )
    ):
        raise AppError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_M4_ALPHA_GRID",
            message="M4 alpha grid requires 2..21 unique values between 0 and 1",
        )
    return service.latest_run(
        model_code,
        dataset_fingerprint=dataset_fingerprint,
        horizon_days=horizon_days,
        holdout_days=holdout_days,
        min_train_days=min_train_days,
        step_days=step_days,
        season_length=season_length,
        sarima_maxiter=sarima_maxiter,
        m2_n_estimators=m2_n_estimators,
        m2_learning_rate=m2_learning_rate,
        m2_num_leaves=m2_num_leaves,
        m2_max_depth=m2_max_depth,
        m2_min_child_samples=m2_min_child_samples,
        m2_seed=m2_seed,
        m3_n_estimators=m3_n_estimators,
        m3_learning_rate=m3_learning_rate,
        m3_num_leaves=m3_num_leaves,
        m3_max_depth=m3_max_depth,
        m3_min_child_samples=m3_min_child_samples,
        m3_seed=m3_seed,
        m4_alpha_grid=m4_alpha_grid,
    )


@router.get("/runs/{run_id}", response_model=BacktestRunResponse)
def get_model_run(
    run_id: int,
    service: BacktestService = Depends(get_service),
    _user: User = Depends(backtest_reader),
) -> BacktestRunResponse:
    return service.get_run(run_id)
