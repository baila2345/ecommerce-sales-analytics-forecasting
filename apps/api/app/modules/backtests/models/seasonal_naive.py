from dataclasses import dataclass
from datetime import date, timedelta
from typing import ClassVar

from app.modules.backtests.engine import run_rolling_backtest
from app.modules.backtests.types import BacktestResult, SeriesPoint


@dataclass(frozen=True)
class SeasonalNaiveModel:
    season_length: int = 7
    code: ClassVar[str] = "M0"

    def forecast(
        self,
        train: list[SeriesPoint],
        forecast_dates: list[date],
    ) -> list[float]:
        return seasonal_naive_forecast(
            train,
            forecast_dates,
            season_length=self.season_length,
        )


def seasonal_naive_forecast(
    train: list[SeriesPoint],
    forecast_dates: list[date],
    season_length: int = 7,
) -> list[float]:
    history = {point.date: point.value for point in train}
    if not forecast_dates:
        return []
    requested = set(forecast_dates)
    predicted_by_date: dict[date, float] = {}
    current_date = train[-1].date + timedelta(days=1)
    final_date = max(forecast_dates)
    while current_date <= final_date:
        source_date = current_date - timedelta(days=season_length)
        if source_date not in history:
            raise ValueError("Training history does not cover the seasonal lag")
        prediction = history[source_date]
        history[current_date] = prediction
        if current_date in requested:
            predicted_by_date[current_date] = prediction
        current_date += timedelta(days=1)
    return [predicted_by_date[forecast_date] for forecast_date in forecast_dates]


def run_seasonal_naive_backtest(
    series: list[SeriesPoint],
    *,
    horizon_days: int,
    holdout_days: int,
    min_train_days: int,
    step_days: int,
    season_length: int = 7,
) -> BacktestResult:
    return run_rolling_backtest(
        series,
        model=SeasonalNaiveModel(season_length=season_length),
        horizon_days=horizon_days,
        holdout_days=holdout_days,
        min_train_days=min_train_days,
        step_days=step_days,
    )
