from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, exists, func, not_, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    Customer,
    Geolocation,
    Order,
    OrderItem,
    OrderPayment,
    OrderReview,
    Product,
    ProductCategory,
    Seller,
)
from app.modules.data_quality.rules import (
    eligible_ml_order_condition,
    usable_delivery_feature_condition,
)


class DataQualityRepository:
    TABLES = (
        ("customers", Customer),
        ("sellers", Seller),
        ("product_categories", ProductCategory),
        ("products", Product),
        ("orders", Order),
        ("order_items", OrderItem),
        ("order_payments", OrderPayment),
        ("order_reviews", OrderReview),
        ("geolocations", Geolocation),
    )

    def __init__(self, session: Session) -> None:
        self.session = session

    def table_counts(self) -> dict[str, int]:
        return {
            name: int(self.session.scalar(select(func.count()).select_from(model)) or 0)
            for name, model in self.TABLES
        }

    def date_range(self) -> tuple[datetime | None, datetime | None]:
        row = self.session.execute(
            select(
                func.min(Order.order_purchase_timestamp),
                func.max(Order.order_purchase_timestamp),
            )
        ).one()
        return row[0], row[1]

    def issue_counts(self, mismatched_orders: int | None = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        counts.update(self._orphan_counts())
        counts.update(self._order_counts())
        counts.update(self._product_counts())
        counts.update(self._financial_counts(mismatched_orders))
        counts.update(self._geography_counts())
        return counts

    def financial_reconciliation(self) -> dict[str, Decimal | int]:
        item_totals = (
            select(
                OrderItem.order_id.label("order_id"),
                func.sum(OrderItem.price).label("item_value"),
                func.sum(OrderItem.freight_value).label("freight_value"),
            )
            .group_by(OrderItem.order_id)
            .subquery()
        )
        payment_totals = (
            select(
                OrderPayment.order_id.label("order_id"),
                func.sum(OrderPayment.payment_value).label("payment_value"),
            )
            .group_by(OrderPayment.order_id)
            .subquery()
        )
        zero = Decimal("0")
        item_value = func.coalesce(item_totals.c.item_value, zero)
        freight_value = func.coalesce(item_totals.c.freight_value, zero)
        payment_value = func.coalesce(payment_totals.c.payment_value, zero)
        mismatch = (
            func.abs(payment_value - item_value - freight_value) > Decimal("0.01")
        )

        row = self.session.execute(
            select(
                func.coalesce(func.sum(item_value), zero),
                func.coalesce(func.sum(freight_value), zero),
                func.coalesce(func.sum(payment_value), zero),
                func.coalesce(func.sum(case((mismatch, 1), else_=0)), 0),
            )
            .select_from(Order)
            .outerjoin(item_totals, item_totals.c.order_id == Order.order_id)
            .outerjoin(payment_totals, payment_totals.c.order_id == Order.order_id)
        ).one()
        return {
            "item_value": Decimal(row[0]),
            "freight_value": Decimal(row[1]),
            "payment_value": Decimal(row[2]),
            "mismatched_orders": int(row[3]),
        }

    def ml_eligibility(self) -> dict[str, Decimal | int]:
        eligible = eligible_ml_order_condition()
        excluded = not_(eligible)
        delivered = Order.order_status == "delivered"

        order_row = self.session.execute(
            select(
                func.count(Order.order_id),
                func.coalesce(func.sum(case((eligible, 1), else_=0)), 0),
                func.coalesce(func.sum(case((excluded, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (not_(usable_delivery_feature_condition()), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(delivered)
        ).one()

        excluded_items = self.session.execute(
            select(
                func.count(OrderItem.order_id),
                func.coalesce(func.sum(OrderItem.price), Decimal("0")),
            )
            .select_from(Order)
            .join(OrderItem, OrderItem.order_id == Order.order_id)
            .where(delivered, excluded)
        ).one()
        return {
            "delivered_orders": int(order_row[0]),
            "eligible_orders": int(order_row[1]),
            "excluded_orders": int(order_row[2]),
            "delivery_feature_excluded_orders": int(order_row[3]),
            "excluded_item_rows": int(excluded_items[0]),
            "excluded_revenue": Decimal(excluded_items[1]),
        }

    def _count(self, model: type, *conditions: object) -> int:
        statement = select(func.count()).select_from(model)
        if conditions:
            statement = statement.where(*conditions)
        return int(self.session.scalar(statement) or 0)

    def _count_joined(
        self,
        model: type,
        join_model: type,
        on_clause: object,
        conditions: Iterable[object],
    ) -> int:
        statement = (
            select(func.count())
            .select_from(model)
            .outerjoin(join_model, on_clause)
            .where(*conditions)
        )
        return int(self.session.scalar(statement) or 0)

    def _orphan_counts(self) -> dict[str, int]:
        return {
            "orphan_orders": self._count_joined(
                Order,
                Customer,
                Order.customer_id == Customer.customer_id,
                (Customer.customer_id.is_(None),),
            ),
            "orphan_item_orders": self._count_joined(
                OrderItem,
                Order,
                OrderItem.order_id == Order.order_id,
                (Order.order_id.is_(None),),
            ),
            "orphan_item_products": self._count_joined(
                OrderItem,
                Product,
                OrderItem.product_id == Product.product_id,
                (Product.product_id.is_(None),),
            ),
            "orphan_item_sellers": self._count_joined(
                OrderItem,
                Seller,
                OrderItem.seller_id == Seller.seller_id,
                (Seller.seller_id.is_(None),),
            ),
            "orphan_payments": self._count_joined(
                OrderPayment,
                Order,
                OrderPayment.order_id == Order.order_id,
                (Order.order_id.is_(None),),
            ),
            "orphan_reviews": self._count_joined(
                OrderReview,
                Order,
                OrderReview.order_id == Order.order_id,
                (Order.order_id.is_(None),),
            ),
        }

    def _order_counts(self) -> dict[str, int]:
        return {
            "delivered_without_delivery_date": self._count(
                Order,
                Order.order_status == "delivered",
                Order.order_delivered_customer_date.is_(None),
            ),
            "delivered_without_items": self._count(
                Order,
                Order.order_status == "delivered",
                ~exists(
                    select(OrderItem.order_id).where(
                        OrderItem.order_id == Order.order_id
                    )
                ),
            ),
            "orders_without_payments": self._count(
                Order,
                ~exists(
                    select(OrderPayment.order_id).where(
                        OrderPayment.order_id == Order.order_id
                    )
                ),
            ),
            "approved_before_purchase": self._count(
                Order,
                Order.order_approved_at.is_not(None),
                Order.order_approved_at < Order.order_purchase_timestamp,
            ),
            "carrier_before_purchase": self._count(
                Order,
                Order.order_delivered_carrier_date.is_not(None),
                Order.order_delivered_carrier_date < Order.order_purchase_timestamp,
            ),
            "delivery_before_carrier": self._count(
                Order,
                Order.order_delivered_customer_date.is_not(None),
                Order.order_delivered_carrier_date.is_not(None),
                Order.order_delivered_customer_date
                < Order.order_delivered_carrier_date,
            ),
            "estimate_before_purchase": self._count(
                Order,
                Order.order_estimated_delivery_date
                < Order.order_purchase_timestamp,
            ),
            "non_delivered_with_delivery_date": self._count(
                Order,
                Order.order_status != "delivered",
                Order.order_delivered_customer_date.is_not(None),
            ),
        }

    def _product_counts(self) -> dict[str, int]:
        missing_dimensions = or_(
            Product.product_weight_g.is_(None),
            Product.product_length_cm.is_(None),
            Product.product_height_cm.is_(None),
            Product.product_width_cm.is_(None),
        )
        return {
            "products_without_category": self._count(
                Product, Product.product_category_name.is_(None)
            ),
            "categories_without_translation": self._count(
                ProductCategory,
                or_(
                    ProductCategory.category_name_english.is_(None),
                    ProductCategory.category_name_english == "",
                ),
            ),
            "products_missing_dimensions": self._count(Product, missing_dimensions),
        }

    def _financial_counts(self, mismatched_orders: int | None) -> dict[str, int]:
        if mismatched_orders is None:
            mismatched_orders = int(
                self.financial_reconciliation()["mismatched_orders"]
            )
        return {
            "non_positive_item_prices": self._count(
                OrderItem, OrderItem.price <= 0
            ),
            "negative_freight_values": self._count(
                OrderItem, OrderItem.freight_value < 0
            ),
            "negative_payment_values": self._count(
                OrderPayment, OrderPayment.payment_value < 0
            ),
            "payment_mismatched_orders": mismatched_orders,
        }

    def _geography_counts(self) -> dict[str, int]:
        return {
            "invalid_geolocation_coordinates": self._count(
                Geolocation,
                or_(
                    Geolocation.geolocation_lat < -90,
                    Geolocation.geolocation_lat > 90,
                    Geolocation.geolocation_lng < -180,
                    Geolocation.geolocation_lng > 180,
                ),
            ),
            "invalid_customer_states": self._count(
                Customer, func.length(Customer.customer_state) != 2
            ),
            "invalid_seller_states": self._count(
                Seller, func.length(Seller.seller_state) != 2
            ),
        }
