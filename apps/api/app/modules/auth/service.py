from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    dummy_password_hash,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.models import User
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, TokenResponse


INVALID_CREDENTIALS = "Email or password is incorrect"


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AuthRepository(session)

    def login(self, credentials: LoginRequest) -> TokenResponse:
        email = str(credentials.email).strip().lower()
        password = credentials.password.get_secret_value()
        user = self.repository.get_user_by_email(email)

        password_hash = user.password_hash if user else dummy_password_hash
        password_is_valid = verify_password(password, password_hash)

        if user is None or not password_is_valid or not user.is_active:
            reason = "unknown_user"
            if user is not None and not password_is_valid:
                reason = "invalid_password"
            elif user is not None and not user.is_active:
                reason = "inactive_user"

            self.repository.add_audit_event(
                action="auth.login.failed",
                actor_id=user.id if user else None,
                entity_type="user" if user else None,
                entity_id=str(user.id) if user else None,
                payload={"reason": reason},
            )
            self.session.commit()
            raise AppError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_CREDENTIALS",
                message=INVALID_CREDENTIALS,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        self.repository.add_audit_event(
            action="auth.login.succeeded",
            actor_id=user.id,
            entity_type="user",
            entity_id=str(user.id),
        )
        self.session.commit()

        settings = get_settings()
        return TokenResponse(
            access_token=create_access_token(user.id, user.role),
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def get_active_user(self, user_id: int) -> User:
        user = self.repository.get_user_by_id(user_id)
        if user is None or not user.is_active:
            raise AppError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_TOKEN",
                message="Authentication token is invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
