from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, User


class AuthRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email.strip().lower())
        return self.session.scalar(statement)

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def add_user(self, user: User) -> User:
        self.session.add(user)
        return user

    def add_audit_event(
        self,
        *,
        action: str,
        actor_id: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        payload: dict[str, str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload,
        )
        self.session.add(event)
        return event
