from sqlalchemy import ColumnElement, and_, func

from app.db.models import Order, OrderItem, Product, ProductCategory


ML_QUALITY_POLICY_VERSION = "olist-ml-quality-v1"
UNKNOWN_CATEGORY = "unknown"


def eligible_ml_order_condition() -> ColumnElement[bool]:
    """Orders safe for maturity-aware revenue datasets.

    A delivery timestamp is required because a backtest must be able to decide
    whether the final delivered state was already known at each forecast origin.
    """

    has_items = (
        Order.items.any()
    )
    return and_(
        Order.order_status == "delivered",
        Order.order_delivered_customer_date.is_not(None),
        Order.order_delivered_customer_date >= Order.order_purchase_timestamp,
        has_items,
    )


def usable_delivery_feature_condition() -> ColumnElement[bool]:
    """Whether carrier/customer timestamps can safely form delivery features."""

    return and_(
        eligible_ml_order_condition(),
        Order.order_delivered_carrier_date.is_not(None),
        Order.order_delivered_carrier_date >= Order.order_purchase_timestamp,
        Order.order_delivered_customer_date
        >= Order.order_delivered_carrier_date,
    )


def normalized_category_expression() -> ColumnElement[str]:
    """Stable category label for downstream analytical/ML projections."""

    return func.coalesce(
        func.nullif(ProductCategory.category_name_english, ""),
        func.nullif(Product.product_category_name, ""),
        UNKNOWN_CATEGORY,
    )
