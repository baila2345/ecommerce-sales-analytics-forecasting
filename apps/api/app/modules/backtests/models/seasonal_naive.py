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
    predictions: list[float] = []
    for forecast_date in forecast_dates:
        source_date = forecast_date - timedelta(days=season_length)
        if source_date not in history:
            raise ValueError("Training history does not cover the seasonal lag")
        prediction = history[source_date]
        predictions.append(prediction)
        history[forecast_date] = prediction
    return predictions


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
