from email_validator import EmailNotValidError, validate_email

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db.models import User, UserRole
from app.modules.auth.repository import AuthRepository


def main() -> None:
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be configured")
    if len(settings.admin_password) < 12:
        raise RuntimeError("ADMIN_PASSWORD must contain at least 12 characters")

    try:
        email = validate_email(
            settings.admin_email,
            check_deliverability=False,
        ).normalized.lower()
    except EmailNotValidError as exc:
        raise RuntimeError("ADMIN_EMAIL is invalid") from exc

    with SessionLocal() as session:
        repository = AuthRepository(session)
        existing_user = repository.get_user_by_email(email)
        if existing_user is not None:
            if existing_user.role != UserRole.ADMIN.value:
                raise RuntimeError("Configured ADMIN_EMAIL belongs to a non-admin user")
            print(f"Admin already exists: {email}")
            return

        admin = User(
            email=email,
            password_hash=hash_password(settings.admin_password),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        repository.add_user(admin)
        session.flush()
        repository.add_audit_event(
            action="auth.admin.seeded",
            actor_id=admin.id,
            entity_type="user",
            entity_id=str(admin.id),
            payload={"source": "seed_admin"},
        )
        session.commit()
        print(f"Admin created: {email}")


if __name__ == "__main__":
    main()
