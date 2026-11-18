from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from app.modules.backtests.datasets import RevenueAsOfIndex
from app.modules.backtests.features.direct_decomposition import (
    AOV_FEATURE_NAMES,
    DECOMPOSITION_FEATURE_SCHEMA_HASH,
    ORDERS_FEATURE_NAMES,
    build_decomposition_forecast_data,
    build_decomposition_training_data,
)
from app.modules.backtests.types import BacktestDataset, ForecastOutput


@dataclass(frozen=True)
class OrdersAovModel:
    n_estimators: int = 200
    learning_rate: float = 0.05
    num_leaves: int = 15
    max_depth: int = 5
    min_child_samples: int = 20
    seed: int = 42
    code: ClassVar[str] = "M3"
    feature_schema_hash: ClassVar[str] = DECOMPOSITION_FEATURE_SCHEMA_HASH

    def forecast(
        self,
        dataset: BacktestDataset,
        index: RevenueAsOfIndex,
        origin_date: date,
        forecast_dates: list[date],
    ) -> ForecastOutput:
        if not forecast_dates:
            return ForecastOutput([])
        horizon_days = max((value - origin_date).days for value in forecast_dates)
        training = build_decomposition_training_data(
            dataset,
            index,
            origin_date,
            horizon_days,
        )
        forecast = build_decomposition_forecast_data(
            dataset,
            index,
            origin_date,
            forecast_dates,
        )
        predicted_orders = self._fit_predict(
            training.orders_rows,
            training.orders_targets,
            forecast.orders_rows,
            list(ORDERS_FEATURE_NAMES),
            objective="poisson",
            scale=forecast.orders_scale,
        )
        predicted_aov = self._fit_predict(
            training.aov_rows,
            training.aov_targets,
            forecast.aov_rows,
            list(AOV_FEATURE_NAMES),
            objective="regression_l1",
            scale=forecast.aov_scale,
        )
        predictions = [
            orders * aov
            for orders, aov in zip(
                predicted_orders,
                predicted_aov,
                strict=True,
            )
        ]
        return ForecastOutput(
            predictions=predictions,
            components=[
                {
                    "predicted_orders": orders,
                    "predicted_aov": aov,
                }
                for orders, aov in zip(
                    predicted_orders,
                    predicted_aov,
                    strict=True,
                )
            ],
        )

    def _fit_predict(
        self,
        train_rows: list[list[float]],
        train_targets: list[float],
        forecast_rows: list[list[float]],
        feature_names: list[str],
        *,
        objective: str,
        scale: float,
    ) -> list[float]:
        from lightgbm import LGBMRegressor
        from pandas import DataFrame

        estimator = LGBMRegressor(
            objective=objective,
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            min_child_samples=self.min_child_samples,
            random_state=self.seed,
            deterministic=True,
            force_col_wise=True,
            n_jobs=1,
            verbosity=-1,
        )
        estimator.fit(DataFrame(train_rows, columns=feature_names), train_targets)
        values = estimator.predict(DataFrame(forecast_rows, columns=feature_names))
        return [max(0.0, float(value) * scale) for value in values]
