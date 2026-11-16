from datetime import date
from dataclasses import dataclass
from typing import Protocol

from app.modules.backtests.datasets import RevenueAsOfIndex, known_series_at
from app.modules.backtests.types import BacktestDataset, SeriesPoint


class ForecastModel(Protocol):
    code: str

    def forecast(
        self,
        train: list[SeriesPoint],
        forecast_dates: list[date],
    ) -> list[float]: ...


class TemporalForecastModel(Protocol):
    code: str

    def forecast(
        self,
        dataset: BacktestDataset,
        index: RevenueAsOfIndex,
        origin_date: date,
        forecast_dates: list[date],
    ) -> list[float]: ...


@dataclass(frozen=True)
class SeriesModelAdapter:
    model: ForecastModel

    @property
    def code(self) -> str:
        return self.model.code

    def forecast(
        self,
        dataset: BacktestDataset,
        index: RevenueAsOfIndex,
        origin_date: date,
        forecast_dates: list[date],
    ) -> list[float]:
        train = known_series_at(dataset, index, origin_date)
        return self.model.forecast(train, forecast_dates)
