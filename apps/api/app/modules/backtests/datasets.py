from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta

from app.modules.backtests.types import BacktestDataset, RevenueEvent, SeriesPoint


class RevenueAsOfIndex:
    """Revenue by purchase date, limited to deliveries known at an origin."""

    def __init__(self, events: list[RevenueEvent]) -> None:
        grouped: dict[date, list[tuple[date, float]]] = defaultdict(list)
        for event in events:
            grouped[event.purchase_date].append(
                (event.delivered_date, event.value)
            )
        self._deliveries: dict[date, list[date]] = {}
        self._prefix_sums: dict[date, list[float]] = {}
        for purchase_date, values in grouped.items():
            values.sort(key=lambda item: item[0])
            running = 0.0
            deliveries: list[date] = []
            prefix_sums: list[float] = []
            for delivered_date, value in values:
                running += value
                deliveries.append(delivered_date)
                prefix_sums.append(running)
            self._deliveries[purchase_date] = deliveries
            self._prefix_sums[purchase_date] = prefix_sums

    def value(self, purchase_date: date, known_at: date) -> float:
        deliveries = self._deliveries.get(purchase_date)
        if not deliveries:
            return 0.0
        position = bisect_right(deliveries, known_at) - 1
        if position < 0:
            return 0.0
        return self._prefix_sums[purchase_date][position]

    def series(
        self,
        *,
        start: date,
        end: date,
        known_at: date,
    ) -> list[SeriesPoint]:
        points: list[SeriesPoint] = []
        current = start
        while current <= end:
            points.append(SeriesPoint(current, self.value(current, known_at)))
            current += timedelta(days=1)
        return points


def dataset_from_series(
    series: list[SeriesPoint], *, maturity_days: int = 0
) -> BacktestDataset:
    return BacktestDataset(
        actuals=series,
        revenue_events=[
            RevenueEvent(point.date, point.date, point.value)
            for point in series
            if point.value != 0
        ],
        maturity_days=maturity_days,
    )


def known_series_at(
    dataset: BacktestDataset,
    index: RevenueAsOfIndex,
    origin_date: date,
) -> list[SeriesPoint]:
    if not dataset.actuals:
        return []
    cutoff = origin_date - timedelta(days=dataset.maturity_days)
    return index.series(
        start=dataset.actuals[0].date,
        end=cutoff,
        known_at=origin_date,
    )
