from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class DatasetFingerprintResponse(BaseModel):
    fingerprint: str
    source_checksums: dict[str, str]
    rules_version: str
    quality_policy_version: str
    source_timezone: str
    maturity_days: int
    source_min_date: date
    source_max_date: date


class DatasetSnapshotResponse(DatasetFingerprintResponse):
    id: int
    status: Literal["building", "ready", "failed", "stale"]
    mature_until: date
    daily_sales_days: int
    mature_days: int
    sales_value: float
    orders_count: int
    customer_days: int
    items_count: int
    created_at: datetime
    completed_at: datetime | None
