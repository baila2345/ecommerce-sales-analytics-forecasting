"""Create model runs and backtest folds.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model_code", sa.String(length=10), nullable=False),
        sa.Column("target", sa.String(length=30), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("holdout_from", sa.Date(), nullable=False),
        sa.Column("holdout_to", sa.Date(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "horizon_days IN (7, 30)",
            name=op.f("ck_model_runs_horizon_days"),
        ),
        sa.CheckConstraint(
            "model_code IN ('M0', 'M1', 'M2', 'M3', 'M4')",
            name=op.f("ck_model_runs_model_code"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_model_runs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_model_runs_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["dataset_snapshots.id"],
            name=op.f("fk_model_runs_snapshot_id_dataset_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_runs")),
    )
    op.create_index(
        op.f("ix_model_runs_created_by_id"),
        "model_runs",
        ["created_by_id"],
    )
    op.create_index(
        op.f("ix_model_runs_dataset_fingerprint"),
        "model_runs",
        ["dataset_fingerprint"],
    )
    op.create_index(
        op.f("ix_model_runs_model_code"), "model_runs", ["model_code"]
    )
    op.create_index(
        op.f("ix_model_runs_snapshot_id"), "model_runs", ["snapshot_id"]
    )
    op.create_index(
        op.f("ix_model_runs_status"), "model_runs", ["status"]
    )
    op.create_index(
        "ix_model_runs_snapshot_created",
        "model_runs",
        ["snapshot_id", "created_at"],
    )

    op.create_table(
        "backtest_folds",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("fold_no", sa.Integer(), nullable=False),
        sa.Column("origin_date", sa.Date(), nullable=False),
        sa.Column("train_from", sa.Date(), nullable=False),
        sa.Column("train_to", sa.Date(), nullable=False),
        sa.Column("test_from", sa.Date(), nullable=False),
        sa.Column("test_to", sa.Date(), nullable=False),
        sa.Column("mae", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("rmse", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("wape", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("actual_sum", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "prediction_sum", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("predictions_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "fold_no >= 1", name=op.f("ck_backtest_folds_positive_fold_no")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["model_runs.id"],
            name=op.f("fk_backtest_folds_run_id_model_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backtest_folds")),
        sa.UniqueConstraint(
            "run_id", "fold_no", name=op.f("uq_backtest_folds_run_fold")
        ),
    )
    op.create_index(
        op.f("ix_backtest_folds_run_id"), "backtest_folds", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_backtest_folds_run_id"), table_name="backtest_folds")
    op.drop_table("backtest_folds")

    op.drop_index("ix_model_runs_snapshot_created", table_name="model_runs")
    op.drop_index(op.f("ix_model_runs_status"), table_name="model_runs")
    op.drop_index(op.f("ix_model_runs_snapshot_id"), table_name="model_runs")
    op.drop_index(op.f("ix_model_runs_model_code"), table_name="model_runs")
    op.drop_index(
        op.f("ix_model_runs_dataset_fingerprint"), table_name="model_runs"
    )
    op.drop_index(op.f("ix_model_runs_created_by_id"), table_name="model_runs")
    op.drop_table("model_runs")
