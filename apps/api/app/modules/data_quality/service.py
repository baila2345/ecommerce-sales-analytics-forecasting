from dataclasses import dataclass
from decimal import Decimal

from app.db.base import utc_now
from app.modules.data_quality.repository import DataQualityRepository
from app.modules.data_quality.rules import ML_QUALITY_POLICY_VERSION
from app.modules.data_quality.schemas import (
    DataQualityReportResponse,
    DatasetDateRange,
    FinancialReconciliation,
    MlEligibilitySummary,
    QualityCheck,
    QualitySummary,
    TableCount,
)


@dataclass(frozen=True)
class CheckDefinition:
    code: str
    severity: str
    message: str


CHECKS = (
    CheckDefinition("orphan_orders", "error", "Orders reference missing customers."),
    CheckDefinition("orphan_item_orders", "error", "Items reference missing orders."),
    CheckDefinition(
        "orphan_item_products", "error", "Items reference missing products."
    ),
    CheckDefinition("orphan_item_sellers", "error", "Items reference missing sellers."),
    CheckDefinition("orphan_payments", "error", "Payments reference missing orders."),
    CheckDefinition("orphan_reviews", "error", "Reviews reference missing orders."),
    CheckDefinition(
        "delivered_without_delivery_date",
        "error",
        "Delivered orders are missing the customer delivery timestamp.",
    ),
    CheckDefinition(
        "delivered_without_items", "error", "Delivered orders have no order items."
    ),
    CheckDefinition(
        "orders_without_payments", "warning", "Orders have no payment records."
    ),
    CheckDefinition(
        "approved_before_purchase",
        "warning",
        "Approval timestamps occur before purchase timestamps.",
    ),
    CheckDefinition(
        "carrier_before_purchase",
        "warning",
        "Carrier timestamps occur before purchase timestamps.",
    ),
    CheckDefinition(
        "delivery_before_carrier",
        "warning",
        "Customer delivery timestamps occur before carrier timestamps.",
    ),
    CheckDefinition(
        "estimate_before_purchase",
        "warning",
        "Estimated delivery timestamps occur before purchase timestamps.",
    ),
    CheckDefinition(
        "non_delivered_with_delivery_date",
        "warning",
        "Non-delivered orders contain customer delivery timestamps.",
    ),
    CheckDefinition(
        "products_without_category", "warning", "Products have no category."
    ),
    CheckDefinition(
        "categories_without_translation",
        "warning",
        "Product categories have no English translation.",
    ),
    CheckDefinition(
        "products_missing_dimensions",
        "warning",
        "Products are missing one or more physical dimensions.",
    ),
    CheckDefinition(
        "non_positive_item_prices", "warning", "Order items have a zero price."
    ),
    CheckDefinition(
        "negative_freight_values", "error", "Order items have negative freight."
    ),
    CheckDefinition(
        "negative_payment_values", "error", "Payments have negative values."
    ),
    CheckDefinition(
        "payment_mismatched_orders",
        "warning",
        "Order payments differ from item value plus freight by more than 0.01.",
    ),
    CheckDefinition(
        "invalid_geolocation_coordinates",
        "error",
        "Geolocation coordinates are outside valid latitude/longitude ranges.",
    ),
    CheckDefinition(
        "invalid_customer_states", "error", "Customer state codes are not 2 characters."
    ),
    CheckDefinition(
        "invalid_seller_states", "error", "Seller state codes are not 2 characters."
    ),
)

DAILY_SALES_BLOCKERS = (
    "orphan_orders",
    "orphan_item_orders",
    "orphan_item_products",
    "orphan_item_sellers",
    "negative_freight_values",
)


class DataQualityService:
    def __init__(self, repository: DataQualityRepository) -> None:
        self.repository = repository

    def report(self) -> DataQualityReportResponse:
        table_counts = self.repository.table_counts()
        reconciliation = self.repository.financial_reconciliation()
        issue_counts = self.repository.issue_counts(
            int(reconciliation["mismatched_orders"])
        )
        min_purchase_at, max_purchase_at = self.repository.date_range()
        ml_eligibility = self.repository.ml_eligibility()

        checks = [
            QualityCheck(
                code=f"{table}_not_empty",
                severity="error",
                passed=rows > 0,
                affected_rows=0 if rows > 0 else 1,
                message=f"{table} must contain at least one row.",
            )
            for table, rows in table_counts.items()
        ]
        checks.extend(
            QualityCheck(
                code=definition.code,
                severity=definition.severity,  # type: ignore[arg-type]
                passed=issue_counts[definition.code] == 0,
                affected_rows=issue_counts[definition.code],
                message=definition.message,
            )
            for definition in CHECKS
        )

        failed = sum(
            not check.passed and check.severity == "error" for check in checks
        )
        warnings = sum(
            not check.passed and check.severity == "warning" for check in checks
        )
        passed = sum(check.passed for check in checks)
        status = "failed" if failed else "warning" if warnings else "passed"

        item_value = Decimal(reconciliation["item_value"])
        freight_value = Decimal(reconciliation["freight_value"])
        payment_value = Decimal(reconciliation["payment_value"])
        expected_payment_value = item_value + freight_value

        return DataQualityReportResponse(
            generated_at=utc_now(),
            status=status,
            summary=QualitySummary(
                passed=passed,
                warnings=warnings,
                failed=failed,
            ),
            tables=[
                TableCount(table=table, rows=rows)
                for table, rows in table_counts.items()
            ],
            date_range=DatasetDateRange(
                min_purchase_at=min_purchase_at,
                max_purchase_at=max_purchase_at,
            ),
            reconciliation=FinancialReconciliation(
                item_value=float(item_value),
                freight_value=float(freight_value),
                expected_payment_value=float(expected_payment_value),
                payment_value=float(payment_value),
                difference=float(payment_value - expected_payment_value),
                mismatched_orders=int(reconciliation["mismatched_orders"]),
            ),
            ml_eligibility=MlEligibilitySummary(
                policy_version=ML_QUALITY_POLICY_VERSION,
                ready_for_daily_sales=(
                    int(ml_eligibility["eligible_orders"]) > 0
                    and all(issue_counts[code] == 0 for code in DAILY_SALES_BLOCKERS)
                ),
                delivered_orders=int(ml_eligibility["delivered_orders"]),
                eligible_orders=int(ml_eligibility["eligible_orders"]),
                excluded_orders=int(ml_eligibility["excluded_orders"]),
                excluded_item_rows=int(ml_eligibility["excluded_item_rows"]),
                excluded_revenue=float(ml_eligibility["excluded_revenue"]),
                delivery_feature_excluded_orders=int(
                    ml_eligibility["delivery_feature_excluded_orders"]
                ),
                unknown_category_products=issue_counts[
                    "products_without_category"
                ],
            ),
            checks=checks,
        )
