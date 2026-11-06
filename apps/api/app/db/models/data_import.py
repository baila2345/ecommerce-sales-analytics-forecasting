from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utc_now


class ImportStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="status",
        ),
        CheckConstraint(
            "dataset_type IN ('customers', 'orders', 'order_items', 'products', "
            "'product_categories', 'order_payments', 'order_reviews', 'sellers', "
            "'geolocations')",
            name="dataset_type",
        ),
        Index("ix_import_batches_dataset_created", "dataset_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    dataset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_checksum_sha256: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ImportStatus.PENDING.value, index=True
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    errors: Mapped[list["ImportError"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True
    )


class ImportError(Base):
    __tablename__ = "import_errors"
    __table_args__ = (
        Index("ix_import_errors_batch_row", "batch_id", "row_number"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    batch_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    batch: Mapped[ImportBatch] = relationship(back_populates="errors")
