from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, case, func, literal_column, select
from sqlalchemy.orm import Session

from app.db.models import Customer, Order, OrderItem, Product, ProductCategory, Seller
from app.modules.analytics.filters import AnalyticsFilters


class AnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _query(
        self,
        *columns: Any,
        filters: AnalyticsFilters,
        customer: bool = False,
        items: bool = False,
        product: bool = False,
        category: bool = False,
        seller: bool = False,
    ) -> Select[Any]:
        """Build only the joins required by a report and its filters."""
        needs_customer = customer or filters.state is not None
        needs_product = product or category or filters.category is not None
        needs_items = items or needs_product or seller or filters.seller_id is not None

        statement = select(*columns).select_from(Order)
        if needs_customer:
            statement = statement.join(Customer, Customer.customer_id == Order.customer_id)
        if needs_items:
            statement = statement.join(OrderItem, OrderItem.order_id == Order.order_id)
        if needs_product:
            statement = statement.join(Product, Product.product_id == OrderItem.product_id)
        if category:
            statement = statement.outerjoin(
                ProductCategory,
                ProductCategory.category_name == Product.product_category_name,
            )
        if seller:
            statement = statement.join(Seller, Seller.seller_id == OrderItem.seller_id)
        return self._apply_filters(statement, filters)

    @staticmethod
    def _apply_filters(
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
            statement = statement.where(Product.product_category_name == filters.category)
        if filters.seller_id:
            statement = statement.where(OrderItem.seller_id == filters.seller_id)
        return statement

    @staticmethod
    def _money(value: Decimal | float | int | None) -> float:
        return round(float(value or 0), 2)

    def _delivery_days(self, purchased: Any, delivered: Any) -> Any:
        if self.session.get_bind().dialect.name == "sqlite":
            return func.julianday(delivered) - func.julianday(purchased)
        return (
            func.timestampdiff(literal_column("SECOND"), purchased, delivered)
            / 86400.0
        )

    def _delivery_orders(
        self,
        filters: AnalyticsFilters,
        *,
        include_state: bool,
    ) -> Any:
        columns = [
            Order.order_id.label("order_id"),
            Order.order_purchase_timestamp.label("purchased_at"),
            Order.order_delivered_customer_date.label("delivered_at"),
            Order.order_estimated_delivery_date.label("estimated_at"),
        ]
        if include_state:
            columns.append(Customer.customer_state.label("state"))
        return (
            self._query(
                *columns,
                filters=filters,
                customer=include_state,
            )
            .where(Order.order_status == "delivered")
            .where(Order.order_delivered_customer_date.is_not(None))
            .distinct()
            .subquery()
        )

    def overview(self, filters: AnalyticsFilters) -> dict[str, float | int | None]:
        delivered = self._query(
            func.coalesce(func.sum(OrderItem.price), 0),
            func.count(func.distinct(Order.order_id)),
            func.count(func.distinct(Customer.customer_unique_id)),
            func.count(OrderItem.order_item_id),
            func.coalesce(func.sum(OrderItem.freight_value), 0),
            filters=filters,
            customer=True,
            items=True,
        ).where(Order.order_status == "delivered")
        revenue, orders, customers, items, freight = self.session.execute(
            delivered
        ).one()

        all_orders = self.session.scalar(
            self._query(
                func.count(func.distinct(Order.order_id)),
                filters=filters,
            )
        ) or 0
        delivered_orders = int(orders or 0)

        delivery_orders = self._delivery_orders(filters, include_state=False)
        average_delivery_days = self.session.scalar(
            select(
                func.avg(
                    self._delivery_days(
                        delivery_orders.c.purchased_at,
                        delivery_orders.c.delivered_at,
                    )
                )
            ).select_from(delivery_orders)
        )

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
            "average_delivery_days": round(float(average_delivery_days), 1)
            if average_delivery_days is not None
            else None,
        }

    def revenue_trend(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        dialect = self.session.get_bind().dialect.name
        period = (
            func.strftime("%Y-%m", Order.order_purchase_timestamp)
            if dialect == "sqlite"
            else func.date_format(Order.order_purchase_timestamp, "%Y-%m")
        )
        statement = (
            self._query(
                period.label("period"),
                func.coalesce(func.sum(OrderItem.price), 0),
                func.count(func.distinct(Order.order_id)),
                filters=filters,
                items=True,
            )
            .where(Order.order_status == "delivered")
            .group_by(period)
            .order_by(period)
        )
        return [
            {"period": row[0], "revenue": self._money(row[1]), "orders": int(row[2])}
            for row in self.session.execute(statement)
        ]

    def order_statuses(self, filters: AnalyticsFilters) -> list[dict[str, Any]]:
        count = func.count(func.distinct(Order.order_id))
        statement = (
            self._query(Order.order_status, count, filters=filters)
            .group_by(Order.order_status)
            .order_by(count.desc())
        )
        return [
            {"label": status, "value": float(total), "orders": int(total)}
            for status, total in self.session.execute(statement)
        ]

    def top_categories(
        self,
        filters: AnalyticsFilters,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        label = func.coalesce(
            ProductCategory.category_name_english,
            Product.product_category_name,
            "Uncategorized",
        )
        revenue = func.sum(OrderItem.price)
        statement = (
            self._query(
                label,
                func.coalesce(revenue, 0),
                func.count(func.distinct(Order.order_id)),
                filters=filters,
                items=True,
                product=True,
                category=True,
            )
            .where(Order.order_status == "delivered")
            .group_by(label)
            .order_by(revenue.desc())
            .limit(limit)
        )
        return [
            {"label": row[0], "value": self._money(row[1]), "orders": int(row[2])}
            for row in self.session.execute(statement)
        ]

    def top_products(
        self,
        filters: AnalyticsFilters,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        category = func.coalesce(
            ProductCategory.category_name_english,
            Product.product_category_name,
            "Uncategorized",
        )
        revenue = func.sum(OrderItem.price)
        statement = (
            self._query(
                Product.product_id,
                category,
                func.coalesce(revenue, 0),
                func.count(OrderItem.order_item_id),
                func.count(func.distinct(Order.order_id)),
                filters=filters,
                items=True,
                product=True,
                category=True,
            )
            .where(Order.order_status == "delivered")
            .group_by(Product.product_id, category)
            .order_by(revenue.desc())
            .limit(limit)
        )
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

    def top_sellers(
        self,
        filters: AnalyticsFilters,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        revenue = func.sum(OrderItem.price)
        statement = (
            self._query(
                Seller.seller_id,
                Seller.seller_city,
                Seller.seller_state,
                func.coalesce(revenue, 0),
                func.count(func.distinct(Order.order_id)),
                filters=filters,
                items=True,
                seller=True,
            )
            .where(Order.order_status == "delivered")
            .group_by(Seller.seller_id, Seller.seller_city, Seller.seller_state)
            .order_by(revenue.desc())
            .limit(limit)
        )
        return [
            {
                "seller_id": row[0],
                "location": f"{row[1]}, {row[2]}",
                "revenue": self._money(row[3]),
                "orders": int(row[4]),
            }
            for row in self.session.execute(statement)
        ]

    def regions(
        self,
        filters: AnalyticsFilters,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        revenue = func.sum(OrderItem.price)
        statement = (
            self._query(
                Customer.customer_state,
                func.coalesce(revenue, 0),
                func.count(func.distinct(Order.order_id)),
                func.count(func.distinct(Customer.customer_unique_id)),
                filters=filters,
                customer=True,
                items=True,
            )
            .where(Order.order_status == "delivered")
            .group_by(Customer.customer_state)
            .order_by(revenue.desc())
            .limit(limit)
        )
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
        delivery_orders = self._delivery_orders(filters, include_state=True)
        days = self._delivery_days(
            delivery_orders.c.purchased_at,
            delivery_orders.c.delivered_at,
        )
        on_time = case(
            (delivery_orders.c.delivered_at <= delivery_orders.c.estimated_at, 1.0),
            else_=0.0,
        )
        delivered_orders = func.count()
        statement = (
            select(
                delivery_orders.c.state,
                func.avg(days),
                func.avg(on_time) * 100,
                delivered_orders,
            )
            .select_from(delivery_orders)
            .group_by(delivery_orders.c.state)
            .order_by(delivered_orders.desc())
            .limit(10)
        )
        return [
            {
                "state": row[0],
                "average_days": round(float(row[1]), 1),
                "on_time_rate": round(float(row[2]), 1),
                "delivered_orders": int(row[3]),
            }
            for row in self.session.execute(statement)
        ]

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
