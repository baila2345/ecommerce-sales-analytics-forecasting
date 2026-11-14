from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import ClassVar, Sequence
import warnings

from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.modules.backtests.engine import run_rolling_backtest
from app.modules.backtests.types import BacktestResult, SeriesPoint


@dataclass(frozen=True)
class SarimaModel:
    order: tuple[int, int, int] = (1, 1, 1)
    seasonal_order: tuple[int, int, int, int] = (1, 0, 1, 7)
    maxiter: int = 100
    code: ClassVar[str] = "M1"

    def forecast(
        self,
        train: list[SeriesPoint],
        forecast_dates: list[date],
    ) -> list[float]:
        return sarima_forecast(
            [point.value for point in train],
            len(forecast_dates),
            order=self.order,
            seasonal_order=self.seasonal_order,
            maxiter=self.maxiter,
        )


def sarima_forecast(
    train: Sequence[float],
    steps: int,
    *,
    order: tuple[int, int, int],
    seasonal_order: tuple[int, int, int, int],
    maxiter: int,
) -> list[float]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model = SARIMAX(
            train,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fitted = model.fit(disp=False, maxiter=maxiter)
    if not fitted.mle_retvals.get("converged", True):
        raise RuntimeError("SARIMA optimizer did not converge")
    predictions = [max(0.0, float(value)) for value in fitted.forecast(steps)]
    if not all(isfinite(value) for value in predictions):
        raise RuntimeError("SARIMA produced a non-finite prediction")
    return predictions


def run_sarima_backtest(
    series: list[SeriesPoint],
    *,
    horizon_days: int,
    holdout_days: int,
    min_train_days: int,
    step_days: int,
    order: tuple[int, int, int] = (1, 1, 1),
    seasonal_order: tuple[int, int, int, int] = (1, 0, 1, 7),
    maxiter: int = 100,
) -> BacktestResult:
    return run_rolling_backtest(
        series,
        model=SarimaModel(
            order=order,
            seasonal_order=seasonal_order,
            maxiter=maxiter,
        ),
        horizon_days=horizon_days,
        holdout_days=holdout_days,
        min_train_days=min_train_days,
        step_days=step_days,
    )
