"""Create Olist sales and data import tables.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("customer_unique_id", sa.String(length=32), nullable=False),
        sa.Column("customer_zip_code_prefix", sa.Integer(), nullable=False),
        sa.Column("customer_city", sa.String(length=255), nullable=False),
        sa.Column("customer_state", sa.String(length=2), nullable=False),
        sa.PrimaryKeyConstraint("customer_id", name=op.f("pk_customers")),
    )
    op.create_index(
        op.f("ix_customers_customer_unique_id"),
        "customers",
        ["customer_unique_id"],
    )
    op.create_index(
        "ix_customers_state_city",
        "customers",
        ["customer_state", "customer_city"],
    )

    op.create_table(
        "sellers",
        sa.Column("seller_id", sa.String(length=32), nullable=False),
        sa.Column("seller_zip_code_prefix", sa.Integer(), nullable=False),
        sa.Column("seller_city", sa.String(length=255), nullable=False),
        sa.Column("seller_state", sa.String(length=2), nullable=False),
        sa.PrimaryKeyConstraint("seller_id", name=op.f("pk_sellers")),
    )
    op.create_index(
        "ix_sellers_state_city", "sellers", ["seller_state", "seller_city"]
    )

    op.create_table(
        "product_categories",
        sa.Column("category_name", sa.String(length=255), nullable=False),
        sa.Column("category_name_english", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("category_name", name=op.f("pk_product_categories")),
    )
    op.create_index(
        op.f("ix_product_categories_category_name_english"),
        "product_categories",
        ["category_name_english"],
    )

    op.create_table(
        "geolocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("geolocation_zip_code_prefix", sa.Integer(), nullable=False),
        sa.Column("geolocation_lat", sa.Float(), nullable=False),
        sa.Column("geolocation_lng", sa.Float(), nullable=False),
        sa.Column("geolocation_city", sa.String(length=255), nullable=False),
        sa.Column("geolocation_state", sa.String(length=2), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geolocations")),
    )
    op.create_index(
        "ix_geolocations_zip_state",
        "geolocations",
        ["geolocation_zip_code_prefix", "geolocation_state"],
    )

    op.create_table(
        "import_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dataset_type", sa.String(length=40), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("imported_rows", sa.Integer(), nullable=False),
        sa.Column("rejected_rows", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.BigInteger(), nullable=True),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dataset_type IN ('customers', 'orders', 'order_items', 'products', "
            "'product_categories', 'order_payments', 'order_reviews', 'sellers', "
            "'geolocations')",
            name=op.f("ck_import_batches_dataset_type"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name=op.f("ck_import_batches_status"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            name=op.f("fk_import_batches_uploaded_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
    )
    op.create_index(
        "ix_import_batches_dataset_created",
        "import_batches",
        ["dataset_type", "created_at"],
    )
    op.create_index(
        op.f("ix_import_batches_file_checksum_sha256"),
        "import_batches",
        ["file_checksum_sha256"],
    )
    op.create_index(
        op.f("ix_import_batches_status"), "import_batches", ["status"]
    )
    op.create_index(
        op.f("ix_import_batches_uploaded_by_id"),
        "import_batches",
        ["uploaded_by_id"],
    )

    op.create_table(
        "products",
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("product_category_name", sa.String(length=255), nullable=True),
        sa.Column("product_name_length", sa.SmallInteger(), nullable=True),
        sa.Column("product_description_length", sa.Integer(), nullable=True),
        sa.Column("product_photos_qty", sa.SmallInteger(), nullable=True),
        sa.Column("product_weight_g", sa.Integer(), nullable=True),
        sa.Column("product_length_cm", sa.SmallInteger(), nullable=True),
        sa.Column("product_height_cm", sa.SmallInteger(), nullable=True),
        sa.Column("product_width_cm", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_category_name"],
            ["product_categories.category_name"],
            name=op.f(
                "fk_products_product_category_name_product_categories"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("product_id", name=op.f("pk_products")),
    )
    op.create_index(
        op.f("ix_products_product_category_name"),
        "products",
        ["product_category_name"],
    )

    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("order_status", sa.String(length=20), nullable=False),
        sa.Column("order_purchase_timestamp", sa.DateTime(), nullable=False),
        sa.Column("order_approved_at", sa.DateTime(), nullable=True),
        sa.Column("order_delivered_carrier_date", sa.DateTime(), nullable=True),
        sa.Column("order_delivered_customer_date", sa.DateTime(), nullable=True),
        sa.Column("order_estimated_delivery_date", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "order_status IN ('created', 'approved', 'invoiced', 'processing', "
            "'shipped', 'delivered', 'unavailable', 'canceled')",
            name=op.f("ck_orders_status"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
            name=op.f("fk_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("order_id", name=op.f("pk_orders")),
    )
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"])
    op.create_index(op.f("ix_orders_order_status"), "orders", ["order_status"])
    op.create_index(
        op.f("ix_orders_order_purchase_timestamp"),
        "orders",
        ["order_purchase_timestamp"],
    )
    op.create_index(
        "ix_orders_purchase_status",
        "orders",
        ["order_purchase_timestamp", "order_status"],
    )

    op.create_table(
        "import_errors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["import_batches.id"],
            name=op.f("fk_import_errors_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_errors")),
    )
    op.create_index(
        "ix_import_errors_batch_row", "import_errors", ["batch_id", "row_number"]
    )

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("order_item_id", sa.SmallInteger(), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("seller_id", sa.String(length=32), nullable=False),
        sa.Column("shipping_limit_date", sa.DateTime(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("freight_value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint(
            "freight_value >= 0", name=op.f("ck_order_items_non_negative_freight")
        ),
        sa.CheckConstraint(
            "price >= 0", name=op.f("ck_order_items_non_negative_price")
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.order_id"],
            name=op.f("fk_order_items_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.product_id"],
            name=op.f("fk_order_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"],
            ["sellers.seller_id"],
            name=op.f("fk_order_items_seller_id_sellers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "order_id", "order_item_id", name=op.f("pk_order_items")
        ),
    )
    op.create_index(
        "ix_order_items_product_order", "order_items", ["product_id", "order_id"]
    )
    op.create_index(
        "ix_order_items_seller_order", "order_items", ["seller_id", "order_id"]
    )

    op.create_table(
        "order_payments",
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("payment_sequential", sa.SmallInteger(), nullable=False),
        sa.Column("payment_type", sa.String(length=30), nullable=False),
        sa.Column("payment_installments", sa.SmallInteger(), nullable=False),
        sa.Column("payment_value", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint(
            "payment_installments >= 0",
            name=op.f("ck_order_payments_non_negative_installments"),
        ),
        sa.CheckConstraint(
            "payment_value >= 0",
            name=op.f("ck_order_payments_non_negative_value"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.order_id"],
            name=op.f("fk_order_payments_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "order_id", "payment_sequential", name=op.f("pk_order_payments")
        ),
    )
    op.create_index(
        "ix_order_payments_type", "order_payments", ["payment_type"]
    )

    op.create_table(
        "order_reviews",
        sa.Column("review_id", sa.String(length=32), nullable=False),
        sa.Column("order_id", sa.String(length=32), nullable=False),
        sa.Column("review_score", sa.SmallInteger(), nullable=False),
        sa.Column("review_comment_title", sa.String(length=255), nullable=True),
        sa.Column("review_comment_message", sa.Text(), nullable=True),
        sa.Column("review_creation_date", sa.DateTime(), nullable=False),
        sa.Column("review_answer_timestamp", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "review_score BETWEEN 1 AND 5",
            name=op.f("ck_order_reviews_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.order_id"],
            name=op.f("fk_order_reviews_order_id_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("review_id", "order_id", name=op.f("pk_order_reviews")),
    )
    op.create_index("ix_order_reviews_order", "order_reviews", ["order_id"])
    op.create_index(
        "ix_order_reviews_score_creation",
        "order_reviews",
        ["review_score", "review_creation_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_reviews_score_creation", table_name="order_reviews")
    op.drop_index("ix_order_reviews_order", table_name="order_reviews")
    op.drop_table("order_reviews")

    op.drop_index("ix_order_payments_type", table_name="order_payments")
    op.drop_table("order_payments")

    op.drop_index("ix_order_items_seller_order", table_name="order_items")
    op.drop_index("ix_order_items_product_order", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_import_errors_batch_row", table_name="import_errors")
    op.drop_table("import_errors")

    op.drop_index("ix_orders_purchase_status", table_name="orders")
    op.drop_index(op.f("ix_orders_order_purchase_timestamp"), table_name="orders")
    op.drop_index(op.f("ix_orders_order_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_products_product_category_name"), table_name="products")
    op.drop_table("products")

    op.drop_index(op.f("ix_import_batches_uploaded_by_id"), table_name="import_batches")
    op.drop_index(op.f("ix_import_batches_status"), table_name="import_batches")
    op.drop_index(
        op.f("ix_import_batches_file_checksum_sha256"), table_name="import_batches"
    )
    op.drop_index("ix_import_batches_dataset_created", table_name="import_batches")
    op.drop_table("import_batches")

    op.drop_index("ix_geolocations_zip_state", table_name="geolocations")
    op.drop_table("geolocations")

    op.drop_index(
        op.f("ix_product_categories_category_name_english"),
        table_name="product_categories",
    )
    op.drop_table("product_categories")

    op.drop_index("ix_sellers_state_city", table_name="sellers")
    op.drop_table("sellers")

    op.drop_index("ix_customers_state_city", table_name="customers")
    op.drop_index(op.f("ix_customers_customer_unique_id"), table_name="customers")
    op.drop_table("customers")
