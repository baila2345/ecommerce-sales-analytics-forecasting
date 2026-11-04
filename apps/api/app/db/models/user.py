from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    MANAGER = "manager"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'analyst', 'manager')",
            name="user_role",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserRole.MANAGER.value,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
    )

    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        back_populates="actor",
        passive_deletes=True,
    )
