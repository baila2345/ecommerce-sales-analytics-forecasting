"""Create dataset snapshots and daily sales.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_checksums", sa.JSON(), nullable=False),
        sa.Column("rules_version", sa.String(length=50), nullable=False),
        sa.Column("quality_policy_version", sa.String(length=50), nullable=False),
        sa.Column("source_timezone", sa.String(length=50), nullable=False),
        sa.Column("maturity_days", sa.Integer(), nullable=False),
        sa.Column("source_min_date", sa.Date(), nullable=False),
        sa.Column("source_max_date", sa.Date(), nullable=False),
        sa.Column("mature_until", sa.Date(), nullable=False),
        sa.Column("quality_report", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "maturity_days >= 1",
            name=op.f("ck_dataset_snapshots_positive_maturity_days"),
        ),
        sa.CheckConstraint(
            "status IN ('building', 'ready', 'failed', 'stale')",
            name=op.f("ck_dataset_snapshots_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_snapshots")),
    )
    op.create_index(
        op.f("ix_dataset_snapshots_fingerprint"),
        "dataset_snapshots",
        ["fingerprint"],
        unique=True,
    )
    op.create_index(
        op.f("ix_dataset_snapshots_status"),
        "dataset_snapshots",
        ["status"],
    )
    op.create_index(
        "ix_dataset_snapshots_status_created",
        "dataset_snapshots",
        ["status", "created_at"],
    )

    op.create_table(
        "daily_sales",
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("sales_date", sa.Date(), nullable=False),
        sa.Column("sales_value", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("orders_count", sa.Integer(), nullable=False),
        sa.Column("customer_count", sa.Integer(), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("aov", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("is_mature", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "aov IS NULL OR aov >= 0",
            name=op.f("ck_daily_sales_non_negative_aov"),
        ),
        sa.CheckConstraint(
            "customer_count >= 0",
            name=op.f("ck_daily_sales_non_negative_customer_count"),
        ),
        sa.CheckConstraint(
            "items_count >= 0",
            name=op.f("ck_daily_sales_non_negative_items_count"),
        ),
        sa.CheckConstraint(
            "orders_count >= 0",
            name=op.f("ck_daily_sales_non_negative_orders_count"),
        ),
        sa.CheckConstraint(
            "sales_value >= 0",
            name=op.f("ck_daily_sales_non_negative_sales_value"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["dataset_snapshots.id"],
            name=op.f("fk_daily_sales_snapshot_id_dataset_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "snapshot_id", "sales_date", name=op.f("pk_daily_sales")
        ),
    )
    op.create_index(
        "ix_daily_sales_snapshot_mature",
        "daily_sales",
        ["snapshot_id", "is_mature"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_sales_snapshot_mature", table_name="daily_sales")
    op.drop_table("daily_sales")

    op.drop_index(
        "ix_dataset_snapshots_status_created", table_name="dataset_snapshots"
    )
    op.drop_index(
        op.f("ix_dataset_snapshots_status"), table_name="dataset_snapshots"
    )
    op.drop_index(
        op.f("ix_dataset_snapshots_fingerprint"), table_name="dataset_snapshots"
    )
    op.drop_table("dataset_snapshots")
