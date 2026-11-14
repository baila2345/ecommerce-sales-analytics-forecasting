"""Add asynchronous model run lifecycle fields.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_model_runs_status"), "model_runs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_model_runs_status"),
        "model_runs",
        "status IN ('queued', 'running', 'succeeded', 'failed')",
    )
    op.add_column(
        "model_runs", sa.Column("job_id", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "model_runs", sa.Column("error_json", sa.JSON(), nullable=True)
    )
    op.add_column(
        "model_runs", sa.Column("started_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("model_runs", "started_at")
    op.drop_column("model_runs", "error_json")
    op.drop_column("model_runs", "job_id")
    op.drop_constraint(
        op.f("ck_model_runs_status"), "model_runs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_model_runs_status"),
        "model_runs",
        "status IN ('running', 'succeeded', 'failed')",
    )
