from datetime import datetime
from typing import Literal

from pydantic import BaseModel


QualityStatus = Literal["passed", "warning", "failed"]
QualitySeverity = Literal["error", "warning"]


class TableCount(BaseModel):
    table: str
    rows: int


class QualityCheck(BaseModel):
    code: str
    severity: QualitySeverity
    passed: bool
    affected_rows: int
    message: str


class QualitySummary(BaseModel):
    passed: int
    warnings: int
    failed: int


class DatasetDateRange(BaseModel):
    min_purchase_at: datetime | None
    max_purchase_at: datetime | None


class FinancialReconciliation(BaseModel):
    item_value: float
    freight_value: float
    expected_payment_value: float
    payment_value: float
    difference: float
    mismatched_orders: int


class MlEligibilitySummary(BaseModel):
    policy_version: str
    ready_for_daily_sales: bool
    delivered_orders: int
    eligible_orders: int
    excluded_orders: int
    excluded_item_rows: int
    excluded_revenue: float
    delivery_feature_excluded_orders: int
    unknown_category_products: int


class DataQualityReportResponse(BaseModel):
    generated_at: datetime
    status: QualityStatus
    summary: QualitySummary
    tables: list[TableCount]
    date_range: DatasetDateRange
    reconciliation: FinancialReconciliation
    ml_eligibility: MlEligibilitySummary
    checks: list[QualityCheck]
