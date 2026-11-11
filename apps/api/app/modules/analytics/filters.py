from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class AnalyticsFilters:
    date_from: date | None = None
    date_to: date | None = None
    state: str | None = None
    category: str | None = None
    seller_id: str | None = None

    @property
    def start_at(self) -> datetime | None:
        return datetime.combine(self.date_from, time.min) if self.date_from else None

    @property
    def end_before(self) -> datetime | None:
        if not self.date_to:
            return None
        return datetime.combine(self.date_to + timedelta(days=1), time.min)
