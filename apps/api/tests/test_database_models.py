import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, User, UserRole


def build_user(email: str = "admin@example.com") -> User:
    return User(
        email=email,
        password_hash="not-a-plain-text-password",
        role=UserRole.ADMIN.value,
    )


def test_user_and_audit_event_are_persisted(db_session: Session) -> None:
    user = build_user()
    db_session.add(user)
    db_session.flush()

    event = AuditEvent(
        actor_id=user.id,
        action="database.foundation.created",
        entity_type="user",
        entity_id=str(user.id),
        payload_json={"source": "test"},
    )
    db_session.add(event)
    db_session.commit()

    assert event.actor_id == user.id
    assert event.actor == user


def test_user_email_must_be_unique(db_session: Session) -> None:
    db_session.add_all([build_user(), build_user()])

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
    assert db_session.is_active


def test_user_role_constraint_rejects_unknown_role(db_session: Session) -> None:
    user = build_user()
    user.role = "unknown"
    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_audit_event_rejects_unknown_actor(db_session: Session) -> None:
    db_session.add(
        AuditEvent(
            actor_id=999,
            action="invalid.actor",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
