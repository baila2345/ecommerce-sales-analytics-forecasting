"""Add a stable experiment key for idempotent model runs.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_runs",
        sa.Column("experiment_key", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_model_runs_experiment_key", "model_runs", ["experiment_key"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_model_runs_experiment_key", "model_runs", type_="unique"
    )
    op.drop_column("model_runs", "experiment_key")
