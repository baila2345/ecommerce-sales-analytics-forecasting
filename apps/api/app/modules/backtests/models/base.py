from datetime import date
from typing import Protocol

from app.modules.backtests.types import SeriesPoint


class ForecastModel(Protocol):
    code: str

    def forecast(
        self,
        train: list[SeriesPoint],
        forecast_dates: list[date],
    ) -> list[float]: ...
