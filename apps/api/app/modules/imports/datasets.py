from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import DeclarativeBase

from app.db.models import (
    Customer,
    Geolocation,
    Order,
    OrderItem,
    OrderPayment,
    OrderReview,
    Product,
    Seller,
)


Converter = Callable[[str], Any]
RowValidator = Callable[[dict[str, Any]], dict[str, str]]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    converter: Converter
    required: bool = True


@dataclass(frozen=True)
class ReferenceSpec:
    field_name: str
    model: type[DeclarativeBase]
    target_field: str


@dataclass(frozen=True)
class DatasetSpec:
    dataset_type: str
    route_slug: str
    display_name: str
    expected_filename: str
    model: type[DeclarativeBase]
    fields: tuple[FieldSpec, ...]
    key_fields: tuple[str, ...]
    update_fields: tuple[str, ...]
    references: tuple[ReferenceSpec, ...] = ()
    row_validator: RowValidator | None = None
    max_file_size_mb: int = 64
    replace_existing: bool = False
    create_missing_categories: bool = False

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)


def text(max_length: int) -> Converter:
    def convert(value: str) -> str:
        if len(value) > max_length:
            raise ValueError(f"must not exceed {max_length} characters")
        return value

    return convert


def integer(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("must be an integer") from exc


def number(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError("must be a number") from exc


def money(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("must be a decimal number") from exc


def timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be a valid ISO date and time") from exc


def validate_state_and_zip(row: dict[str, Any], prefix: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    state_field = f"{prefix}_state"
    zip_field = f"{prefix}_zip_code_prefix"
    state = row.get(state_field)
    zip_code = row.get(zip_field)
    if isinstance(state, str) and (len(state) != 2 or not state.isalpha()):
        errors[state_field] = "must contain a two-letter state code"
    if isinstance(zip_code, int) and not 0 <= zip_code <= 99999:
        errors[zip_field] = "must be between 0 and 99999"
    return errors


def validate_customer(row: dict[str, Any]) -> dict[str, str]:
    return validate_state_and_zip(row, "customer")


def validate_seller(row: dict[str, Any]) -> dict[str, str]:
    return validate_state_and_zip(row, "seller")


def validate_geolocation(row: dict[str, Any]) -> dict[str, str]:
    errors = validate_state_and_zip(row, "geolocation")
    latitude = row.get("geolocation_lat")
    longitude = row.get("geolocation_lng")
    if isinstance(latitude, float) and not -90 <= latitude <= 90:
        errors["geolocation_lat"] = "must be between -90 and 90"
    if isinstance(longitude, float) and not -180 <= longitude <= 180:
        errors["geolocation_lng"] = "must be between -180 and 180"
    return errors


def validate_non_negative(
    row: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, str]:
    return {
        field: "must be greater than or equal to zero"
        for field in fields
        if row.get(field) is not None and row[field] < 0
    }


def validate_product(row: dict[str, Any]) -> dict[str, str]:
    return validate_non_negative(
        row,
        (
            "product_name_length",
            "product_description_length",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
    )


def validate_order(row: dict[str, Any]) -> dict[str, str]:
    allowed = {
        "created",
        "approved",
        "invoiced",
        "processing",
        "shipped",
        "delivered",
        "unavailable",
        "canceled",
    }
    if row.get("order_status") not in allowed:
        return {"order_status": "contains an unsupported order status"}
    return {}


def validate_order_item(row: dict[str, Any]) -> dict[str, str]:
    return validate_non_negative(row, ("order_item_id", "price", "freight_value"))


def validate_payment(row: dict[str, Any]) -> dict[str, str]:
    return validate_non_negative(
        row,
        ("payment_sequential", "payment_installments", "payment_value"),
    )


def validate_review(row: dict[str, Any]) -> dict[str, str]:
    score = row.get("review_score")
    if isinstance(score, int) and not 1 <= score <= 5:
        return {"review_score": "must be between 1 and 5"}
    return {}


CUSTOMERS = DatasetSpec(
    dataset_type="customers",
    route_slug="customers",
    display_name="Khách hàng",
    expected_filename="olist_customers_dataset.csv",
    model=Customer,
    fields=(
        FieldSpec("customer_id", text(32)),
        FieldSpec("customer_unique_id", text(32)),
        FieldSpec("customer_zip_code_prefix", integer),
        FieldSpec("customer_city", text(255)),
        FieldSpec("customer_state", text(2)),
    ),
    key_fields=("customer_id",),
    update_fields=(
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ),
    row_validator=validate_customer,
    max_file_size_mb=32,
)

SELLERS = DatasetSpec(
    dataset_type="sellers",
    route_slug="sellers",
    display_name="Người bán",
    expected_filename="olist_sellers_dataset.csv",
    model=Seller,
    fields=(
        FieldSpec("seller_id", text(32)),
        FieldSpec("seller_zip_code_prefix", integer),
        FieldSpec("seller_city", text(255)),
        FieldSpec("seller_state", text(2)),
    ),
    key_fields=("seller_id",),
    update_fields=("seller_zip_code_prefix", "seller_city", "seller_state"),
    row_validator=validate_seller,
    max_file_size_mb=8,
)

PRODUCTS = DatasetSpec(
    dataset_type="products",
    route_slug="products",
    display_name="Sản phẩm",
    expected_filename="olist_products_dataset.csv",
    model=Product,
    fields=(
        FieldSpec("product_id", text(32)),
        FieldSpec("product_category_name", text(255), required=False),
        FieldSpec("product_name_length", integer, required=False),
        FieldSpec("product_description_length", integer, required=False),
        FieldSpec("product_photos_qty", integer, required=False),
        FieldSpec("product_weight_g", integer, required=False),
        FieldSpec("product_length_cm", integer, required=False),
        FieldSpec("product_height_cm", integer, required=False),
        FieldSpec("product_width_cm", integer, required=False),
    ),
    key_fields=("product_id",),
    update_fields=(
        "product_category_name",
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ),
    row_validator=validate_product,
    max_file_size_mb=32,
    create_missing_categories=True,
)

ORDERS = DatasetSpec(
    dataset_type="orders",
    route_slug="orders",
    display_name="Đơn hàng",
    expected_filename="olist_orders_dataset.csv",
    model=Order,
    fields=(
        FieldSpec("order_id", text(32)),
        FieldSpec("customer_id", text(32)),
        FieldSpec("order_status", text(20)),
        FieldSpec("order_purchase_timestamp", timestamp),
        FieldSpec("order_approved_at", timestamp, required=False),
        FieldSpec("order_delivered_carrier_date", timestamp, required=False),
        FieldSpec("order_delivered_customer_date", timestamp, required=False),
        FieldSpec("order_estimated_delivery_date", timestamp),
    ),
    key_fields=("order_id",),
    update_fields=(
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ),
    references=(ReferenceSpec("customer_id", Customer, "customer_id"),),
    row_validator=validate_order,
    max_file_size_mb=64,
)

ORDER_ITEMS = DatasetSpec(
    dataset_type="order_items",
    route_slug="order-items",
    display_name="Chi tiết đơn hàng",
    expected_filename="olist_order_items_dataset.csv",
    model=OrderItem,
    fields=(
        FieldSpec("order_id", text(32)),
        FieldSpec("order_item_id", integer),
        FieldSpec("product_id", text(32)),
        FieldSpec("seller_id", text(32)),
        FieldSpec("shipping_limit_date", timestamp),
        FieldSpec("price", money),
        FieldSpec("freight_value", money),
    ),
    key_fields=("order_id", "order_item_id"),
    update_fields=(
        "product_id",
        "seller_id",
        "shipping_limit_date",
        "price",
        "freight_value",
    ),
    references=(
        ReferenceSpec("order_id", Order, "order_id"),
        ReferenceSpec("product_id", Product, "product_id"),
        ReferenceSpec("seller_id", Seller, "seller_id"),
    ),
    row_validator=validate_order_item,
    max_file_size_mb=64,
)

ORDER_PAYMENTS = DatasetSpec(
    dataset_type="order_payments",
    route_slug="order-payments",
    display_name="Thanh toán",
    expected_filename="olist_order_payments_dataset.csv",
    model=OrderPayment,
    fields=(
        FieldSpec("order_id", text(32)),
        FieldSpec("payment_sequential", integer),
        FieldSpec("payment_type", text(30)),
        FieldSpec("payment_installments", integer),
        FieldSpec("payment_value", money),
    ),
    key_fields=("order_id", "payment_sequential"),
    update_fields=("payment_type", "payment_installments", "payment_value"),
    references=(ReferenceSpec("order_id", Order, "order_id"),),
    row_validator=validate_payment,
    max_file_size_mb=32,
)

ORDER_REVIEWS = DatasetSpec(
    dataset_type="order_reviews",
    route_slug="order-reviews",
    display_name="Đánh giá",
    expected_filename="olist_order_reviews_dataset.csv",
    model=OrderReview,
    fields=(
        FieldSpec("review_id", text(32)),
        FieldSpec("order_id", text(32)),
        FieldSpec("review_score", integer),
        FieldSpec("review_comment_title", text(255), required=False),
        FieldSpec("review_comment_message", text(65535), required=False),
        FieldSpec("review_creation_date", timestamp),
        FieldSpec("review_answer_timestamp", timestamp),
    ),
    key_fields=("review_id", "order_id"),
    update_fields=(
        "review_score",
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ),
    references=(ReferenceSpec("order_id", Order, "order_id"),),
    row_validator=validate_review,
    max_file_size_mb=128,
)

GEOLOCATIONS = DatasetSpec(
    dataset_type="geolocations",
    route_slug="geolocations",
    display_name="Địa lý",
    expected_filename="olist_geolocation_dataset.csv",
    model=Geolocation,
    fields=(
        FieldSpec("geolocation_zip_code_prefix", integer),
        FieldSpec("geolocation_lat", number),
        FieldSpec("geolocation_lng", number),
        FieldSpec("geolocation_city", text(255)),
        FieldSpec("geolocation_state", text(2)),
    ),
    key_fields=(),
    update_fields=(),
    row_validator=validate_geolocation,
    max_file_size_mb=160,
    replace_existing=True,
)


DATASETS = (
    CUSTOMERS,
    SELLERS,
    PRODUCTS,
    ORDERS,
    ORDER_ITEMS,
    ORDER_PAYMENTS,
    ORDER_REVIEWS,
    GEOLOCATIONS,
)
DATASETS_BY_SLUG = {dataset.route_slug: dataset for dataset in DATASETS}
