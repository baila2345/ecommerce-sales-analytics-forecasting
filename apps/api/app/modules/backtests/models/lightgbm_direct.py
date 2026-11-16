from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from app.modules.backtests.datasets import RevenueAsOfIndex
from app.modules.backtests.features.direct_revenue import (
    DIRECT_FEATURE_NAMES,
    DIRECT_FEATURE_SCHEMA_HASH,
    build_forecast_matrix,
    build_training_matrix,
    revenue_scale_at_origin,
)
from app.modules.backtests.types import BacktestDataset


@dataclass(frozen=True)
class LightGBMDirectModel:
    n_estimators: int = 200
    learning_rate: float = 0.05
    num_leaves: int = 15
    max_depth: int = 5
    min_child_samples: int = 20
    seed: int = 42
    code: ClassVar[str] = "M2"
    feature_schema_hash: ClassVar[str] = DIRECT_FEATURE_SCHEMA_HASH

    def forecast(
        self,
        dataset: BacktestDataset,
        index: RevenueAsOfIndex,
        origin_date: date,
        forecast_dates: list[date],
    ) -> list[float]:
        if not forecast_dates:
            return []
        horizon_days = max((value - origin_date).days for value in forecast_dates)
        features, targets = build_training_matrix(
            dataset,
            index,
            origin_date,
            horizon_days,
        )
        forecast_features = build_forecast_matrix(
            dataset,
            index,
            origin_date,
            forecast_dates,
        )
        from lightgbm import LGBMRegressor
        from pandas import DataFrame

        feature_names = list(DIRECT_FEATURE_NAMES)
        train_frame = DataFrame(features, columns=feature_names)
        forecast_frame = DataFrame(forecast_features, columns=feature_names)
        revenue_scale = revenue_scale_at_origin(dataset, index, origin_date)

        estimator = LGBMRegressor(
            objective="regression_l1",
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
        estimator.fit(train_frame, targets)
        return [
            max(0.0, float(value) * revenue_scale)
            for value in estimator.predict(forecast_frame)
        ]
