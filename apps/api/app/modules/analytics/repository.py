from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import Customer, Order, OrderItem, Product, ProductCategory, Seller
from app.modules.analytics.filters import AnalyticsFilters


class AnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _base_query(self, *columns: Any) -> Select[Any]:
        return (
            select(*columns)
            .select_from(Order)
            .join(Customer, Customer.customer_id == Order.customer_id)
            .outerjoin(OrderItem, OrderItem.order_id == Order.order_id)
            .outerjoin(Product, Product.product_id == OrderItem.product_id)
            .outerjoin(
                ProductCategory,
                ProductCategory.category_name == Product.product_category_name,
            )
            .outerjoin(Seller, Seller.seller_id == OrderItem.seller_id)
        )

    def _apply_filters(
        self,
        statement: Select[Any],
        filters: AnalyticsFilters,
    ) -> Select[Any]:
        if filters.start_at:
            statement = statement.where(Order.order_purchase_timestamp >= filters.start_at)
        if filters.end_before:
            statement = statement.where(Order.order_purchase_timestamp < filters.end_before)
        if filters.state:
            statement = statement.where(Customer.customer_state == filters.state)
        if filters.category:
            statement = statement.where(
                Product.product_category_name == filters.category
            )
        if filters.seller_id:
            statement = statement.where(OrderItem.seller_id == filters.seller_id)
        return statement

    @staticmethod
    def _money(value: Decimal | float | int | None) -> float:
        return round(float(value or 0), 2)

    def overview(self, filters: AnalyticsFilters) -> dict[str, float | int | None]:
        delivered = self._apply_filters(
            self._base_query(
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(func.distinct(Order.order_id)),
                func.count(func.distinct(Customer.customer_unique_id)),
                func.count(OrderItem.order_item_id),
                func.coalesce(func.sum(OrderItem.freight_value), 0),
            ).where(Order.order_status == "delivered"),
            filters,
        )
        revenue, orders, customers, items, freight = self.session.execute(
            delivered
        ).one()

        all_orders = self.session.scalar(
            self._apply_filters(
                self._base_query(func.count(func.distinct(Order.order_id))),
                filters,
            )
        ) or 0
        delivered_orders = int(orders or 0)

        delivery_rows = self.session.execute(
            self._apply_filters(
                self._base_query(
                    Order.order_id,
                    Order.order_purchase_timestamp,
                    Order.order_delivered_customer_date,
                )
                .where(Order.order_status == "delivered")
                .where(Order.order_delivered_customer_date.is_not(None))
                .distinct(),
                filters,
            )
        ).all()
        delivery_days = [
            (delivered_at - purchased_at).total_seconds() / 86400
            for _, purchased_at, delivered_at in delivery_rows
            if delivered_at and purchased_at
        ]
        revenue_value = self._money(revenue)
        return {
            "revenue": revenue_value,
            "orders": delivered_orders,
            "customers": int(customers or 0),
            "average_order_value": round(revenue_value / delivered_orders, 2)
            if delivered_orders
            else 0,
            "items_sold": int(items or 0),
            "freight_value": self._money(freight),
            "delivered_rate": round(delivered_orders / int(all_orders) * 100, 1)
            if all_orders
            else 0,
            "average_delivery_days": round(sum(delivery_days) / len(delivery_days), 1)
            if delivery_days
            else None,
        }

    def revenue_trend(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        dialect = self.session.get_bind().dialect.name
        period = (
            func.strftime("%Y-%m", Order.order_purchase_timestamp)
            if dialect == "sqlite"
            else func.date_format(Order.order_purchase_timestamp, "%Y-%m")
        )
        statement = self._apply_filters(
            self._base_query(
                period.label("period"),
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(func.distinct(Order.order_id)),
            )
            .where(Order.order_status == "delivered")
            .where(Product.product_id.is_not(None)),
            filters,
        ).group_by(period).order_by(period)
        return [
            {"period": row[0], "revenue": self._money(row[1]), "orders": int(row[2])}
            for row in self.session.execute(statement)
        ]

    def order_statuses(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        statement = self._apply_filters(
            self._base_query(
                Order.order_status,
                func.count(func.distinct(Order.order_id)),
            ),
            filters,
        ).group_by(Order.order_status).order_by(func.count(func.distinct(Order.order_id)).desc())
        return [
            {"label": status, "value": float(count), "orders": int(count)}
            for status, count in self.session.execute(statement)
        ]

    def top_categories(self, filters: AnalyticsFilters, limit: int = 8) -> list[dict[str, Any]]:
        label = func.coalesce(
            ProductCategory.category_name_english,
            Product.product_category_name,
            "Uncategorized",
        )
        statement = self._apply_filters(
            self._base_query(
                label,
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(func.distinct(Order.order_id)),
            )
            .where(Order.order_status == "delivered")
            .where(Seller.seller_id.is_not(None)),
            filters,
        ).group_by(label).order_by(func.sum(OrderItem.price).desc()).limit(limit)
        return [
            {"label": row[0], "value": self._money(row[1]), "orders": int(row[2])}
            for row in self.session.execute(statement)
        ]

    def top_products(self, filters: AnalyticsFilters, limit: int = 8) -> list[dict[str, Any]]:
        category = func.coalesce(
            ProductCategory.category_name_english,
            Product.product_category_name,
            "Uncategorized",
        )
        statement = self._apply_filters(
            self._base_query(
                Product.product_id,
                category,
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(OrderItem.order_item_id),
                func.count(func.distinct(Order.order_id)),
            )
            .where(Order.order_status == "delivered")
            .where(Product.product_id.is_not(None)),
            filters,
        ).group_by(Product.product_id, category).order_by(func.sum(OrderItem.price).desc()).limit(limit)
        return [
            {
                "product_id": row[0],
                "category": row[1],
                "revenue": self._money(row[2]),
                "units": int(row[3]),
                "orders": int(row[4]),
            }
            for row in self.session.execute(statement)
        ]

    def top_sellers(self, filters: AnalyticsFilters, limit: int = 8) -> list[dict[str, Any]]:
        statement = self._apply_filters(
            self._base_query(
                Seller.seller_id,
                Seller.seller_city,
                Seller.seller_state,
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(func.distinct(Order.order_id)),
            )
            .where(Order.order_status == "delivered")
            .where(Seller.seller_id.is_not(None)),
            filters,
        ).group_by(Seller.seller_id, Seller.seller_city, Seller.seller_state).order_by(func.sum(OrderItem.price).desc()).limit(limit)
        return [
            {
                "seller_id": row[0],
                "location": f"{row[1]}, {row[2]}",
                "revenue": self._money(row[3]),
                "orders": int(row[4]),
            }
            for row in self.session.execute(statement)
        ]

    def regions(self, filters: AnalyticsFilters, limit: int = 10) -> list[dict[str, Any]]:
        statement = self._apply_filters(
            self._base_query(
                Customer.customer_state,
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(func.distinct(Order.order_id)),
                func.count(func.distinct(Customer.customer_unique_id)),
            ).where(Order.order_status == "delivered"),
            filters,
        ).group_by(Customer.customer_state).order_by(func.sum(OrderItem.price).desc()).limit(limit)
        return [
            {
                "state": row[0],
                "revenue": self._money(row[1]),
                "orders": int(row[2]),
                "customers": int(row[3]),
            }
            for row in self.session.execute(statement)
        ]

    def delivery(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        statement = self._apply_filters(
            self._base_query(
                Order.order_id,
                Customer.customer_state,
                Order.order_purchase_timestamp,
                Order.order_delivered_customer_date,
                Order.order_estimated_delivery_date,
            )
            .where(Order.order_status == "delivered")
            .where(Order.order_delivered_customer_date.is_not(None))
            .distinct(),
            filters,
        )
        grouped: dict[str, list[tuple[float, bool]]] = defaultdict(list)
        for _, state, purchased, delivered, estimated in self.session.execute(statement):
            days = (delivered - purchased).total_seconds() / 86400
            grouped[state].append((days, delivered <= estimated))
        result = []
        for state, rows in grouped.items():
            result.append(
                {
                    "state": state,
                    "average_days": round(sum(row[0] for row in rows) / len(rows), 1),
                    "on_time_rate": round(sum(row[1] for row in rows) / len(rows) * 100, 1),
                    "delivered_orders": len(rows),
                }
            )
        return sorted(result, key=lambda item: item["delivered_orders"], reverse=True)[:10]

    def filter_options(self) -> dict[str, Any]:
        min_date, max_date = self.session.execute(
            select(
                func.min(Order.order_purchase_timestamp),
                func.max(Order.order_purchase_timestamp),
            )
        ).one()
        states = list(
            self.session.scalars(
                select(Customer.customer_state).distinct().order_by(Customer.customer_state)
            )
        )
        categories = list(
            self.session.scalars(
                select(Product.product_category_name)
                .where(Product.product_category_name.is_not(None))
                .distinct()
                .order_by(Product.product_category_name)
            )
        )
        sellers = self.session.execute(
            select(Seller.seller_id, Seller.seller_city, Seller.seller_state)
            .order_by(Seller.seller_state, Seller.seller_city, Seller.seller_id)
        )
        return {
            "min_date": min_date.date() if isinstance(min_date, datetime) else min_date,
            "max_date": max_date.date() if isinstance(max_date, datetime) else max_date,
            "states": states,
            "categories": categories,
            "sellers": [
                {"id": seller_id, "label": f"{city}, {state} · {seller_id[:8]}"}
                for seller_id, city, state in sellers
            ],
        }
