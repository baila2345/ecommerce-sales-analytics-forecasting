from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_state_city", "customer_state", "customer_city"),
    )

    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_unique_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    customer_zip_code_prefix: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_city: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_state: Mapped[str] = mapped_column(String(2), nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Seller(Base):
    __tablename__ = "sellers"
    __table_args__ = (
        Index("ix_sellers_state_city", "seller_state", "seller_city"),
    )

    seller_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    seller_zip_code_prefix: Mapped[int] = mapped_column(Integer, nullable=False)
    seller_city: Mapped[str] = mapped_column(String(255), nullable=False)
    seller_state: Mapped[str] = mapped_column(String(2), nullable=False)

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="seller")


class ProductCategory(Base):
    __tablename__ = "product_categories"

    category_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    category_name_english: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_category_name: Mapped[str | None] = mapped_column(
        String(255),
        ForeignKey("product_categories.category_name", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    product_name_length: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    product_description_length: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    product_photos_qty: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    product_weight_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_length_cm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    product_height_cm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    product_width_cm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    category: Mapped[ProductCategory | None] = relationship(back_populates="products")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "order_status IN ('created', 'approved', 'invoiced', 'processing', "
            "'shipped', 'delivered', 'unavailable', 'canceled')",
            name="status",
        ),
        Index("ix_orders_purchase_status", "order_purchase_timestamp", "order_status"),
    )

    order_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    order_purchase_timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    order_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    order_delivered_carrier_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    order_delivered_customer_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    order_estimated_delivery_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    payments: Mapped[list["OrderPayment"]] = relationship(back_populates="order")
    reviews: Mapped[list["OrderReview"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="non_negative_price"),
        CheckConstraint("freight_value >= 0", name="non_negative_freight"),
        Index("ix_order_items_product_order", "product_id", "order_id"),
        Index("ix_order_items_seller_order", "seller_id", "order_id"),
    )

    order_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
    )
    order_item_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    product_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("products.product_id", ondelete="RESTRICT"),
        nullable=False,
    )
    seller_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("sellers.seller_id", ondelete="RESTRICT"),
        nullable=False,
    )
    shipping_limit_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    freight_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")
    seller: Mapped[Seller] = relationship(back_populates="order_items")


class OrderPayment(Base):
    __tablename__ = "order_payments"
    __table_args__ = (
        CheckConstraint("payment_installments >= 0", name="non_negative_installments"),
        CheckConstraint("payment_value >= 0", name="non_negative_value"),
        Index("ix_order_payments_type", "payment_type"),
    )

    order_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
    )
    payment_sequential: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    payment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_installments: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    payment_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="payments")


class OrderReview(Base):
    __tablename__ = "order_reviews"
    __table_args__ = (
        CheckConstraint("review_score BETWEEN 1 AND 5", name="score_range"),
        Index("ix_order_reviews_order", "order_id"),
        Index(
            "ix_order_reviews_score_creation",
            "review_score",
            "review_creation_date",
        ),
    )

    # A small number of review_id values occur more than once in the source data,
    # so order_id is included to preserve every source row safely.
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
    )
    review_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    review_comment_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_comment_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_creation_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_answer_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    order: Mapped[Order] = relationship(back_populates="reviews")


class Geolocation(Base):
    __tablename__ = "geolocations"
    __table_args__ = (
        Index(
            "ix_geolocations_zip_state",
            "geolocation_zip_code_prefix",
            "geolocation_state",
        ),
    )

    # The source contains many coordinates for one ZIP prefix and duplicate rows.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geolocation_zip_code_prefix: Mapped[int] = mapped_column(Integer, nullable=False)
    geolocation_lat: Mapped[float] = mapped_column(Float, nullable=False)
    geolocation_lng: Mapped[float] = mapped_column(Float, nullable=False)
    geolocation_city: Mapped[str] = mapped_column(String(255), nullable=False)
    geolocation_state: Mapped[str] = mapped_column(String(2), nullable=False)
