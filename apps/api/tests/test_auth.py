from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import AuditEvent, User, UserRole
from app.modules.auth.dependencies import require_roles


TEST_PASSWORD = "valid-test-password"


def create_user(
    db_session: Session,
    *,
    email: str = "admin@example.com",
    password: str = TEST_PASSWORD,
    role: UserRole = UserRole.ADMIN,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role.value,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    return user


def login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_login_and_get_current_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = login(client, user.email.upper(), TEST_PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"]
    assert "x-request-id" in response.headers

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == user.email
    assert me_response.json()["role"] == UserRole.ADMIN.value

    actions = db_session.scalars(select(AuditEvent.action)).all()
    assert "auth.login.succeeded" in actions


def test_login_rejects_wrong_password_without_leaking_reason(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(db_session)

    response = login(client, user.email, "incorrect-password")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "auth.login.failed")
    )
    assert event is not None
    assert event.actor_id == user.id
    assert event.payload_json == {"reason": "invalid_password"}


def test_login_rejects_unknown_and_inactive_users(
    client: TestClient,
    db_session: Session,
) -> None:
    unknown_response = login(client, "unknown@example.com", TEST_PASSWORD)
    inactive = create_user(
        db_session,
        email="inactive@example.com",
        is_active=False,
    )
    inactive_response = login(client, inactive.email, TEST_PASSWORD)

    assert unknown_response.status_code == 401
    assert inactive_response.status_code == 401
    assert unknown_response.json()["error"]["message"] == inactive_response.json()[
        "error"
    ]["message"]


def test_me_requires_a_valid_token(client: TestClient) -> None:
    missing_response = client.get("/api/v1/auth/me")
    invalid_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )

    assert missing_response.status_code == 401
    assert missing_response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert invalid_response.status_code == 401
    assert invalid_response.json()["error"]["code"] == "INVALID_TOKEN"


def test_role_dependency_returns_forbidden(
    client: TestClient,
    db_session: Session,
) -> None:
    manager = create_user(
        db_session,
        email="manager@example.com",
        role=UserRole.MANAGER,
    )
    token = login(client, manager.email, TEST_PASSWORD).json()["access_token"]

    client.app.add_api_route(
        "/test/admin-only",
        lambda: {"status": "ok"},
        methods=["GET"],
        dependencies=[Depends(require_roles(UserRole.ADMIN))],
    )
    response = client.get(
        "/test/admin-only",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_login_validation_uses_standard_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "short"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["request_id"]
