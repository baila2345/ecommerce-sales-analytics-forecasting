from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    ImportBatch,
    ImportError,
    ImportStatus,
    ProductCategory,
    User,
    UserRole,
)


TEST_PASSWORD = "valid-test-password"
VALID_CSV = (
    b"product_category_name,product_category_name_english\n"
    b"beleza_saude,health_beauty\n"
    b"informatica_acessorios,computers_accessories\n"
)


def authenticate(
    client: TestClient,
    db_session: Session,
    role: UserRole = UserRole.ADMIN,
) -> tuple[User, dict[str, str]]:
    user = User(
        email=f"{role.value}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=role.value,
    )
    db_session.add(user)
    db_session.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    )
    token = response.json()["access_token"]
    return user, {"Authorization": f"Bearer {token}"}


def upload(csv_content: bytes, filename: str = "categories.csv"):
    return {"file": (filename, csv_content, "text/csv")}


def test_preview_then_commit_product_categories(
    client: TestClient,
    db_session: Session,
) -> None:
    user, headers = authenticate(client, db_session)

    preview_response = client.post(
        "/api/v1/imports/product-categories/preview",
        files=upload(VALID_CSV),
        headers=headers,
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["can_import"] is True
    assert preview["total_rows"] == 2
    assert preview["valid_rows"] == 2
    assert preview["rejected_rows"] == 0
    assert preview["preview_rows"][0] == {
        "product_category_name": "beleza_saude",
        "product_category_name_english": "health_beauty",
    }
    assert db_session.scalar(select(ProductCategory)) is None

    commit_response = client.post(
        f"/api/v1/imports/product-categories/{preview['batch_id']}/commit",
        files=upload(VALID_CSV),
        headers=headers,
    )

    assert commit_response.status_code == 200
    assert commit_response.json()["status"] == ImportStatus.COMPLETED.value
    assert commit_response.json()["imported_rows"] == 2
    categories = db_session.scalars(
        select(ProductCategory).order_by(ProductCategory.category_name)
    ).all()
    assert len(categories) == 2
    assert categories[0].category_name_english == "health_beauty"
    batch = db_session.get(ImportBatch, preview["batch_id"])
    assert batch is not None
    assert batch.uploaded_by_id == user.id
    assert batch.status == ImportStatus.COMPLETED.value


def test_preview_rejects_wrong_headers_and_records_error(
    client: TestClient,
    db_session: Session,
) -> None:
    _, headers = authenticate(client, db_session)
    response = client.post(
        "/api/v1/imports/product-categories/preview",
        files=upload(b"wrong,columns\nvalue,value\n"),
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["can_import"] is False
    assert body["errors"][0]["code"] == "invalid_headers"
    batch = db_session.get(ImportBatch, body["batch_id"])
    assert batch is not None
    assert batch.status == ImportStatus.FAILED.value
    error = db_session.scalar(
        select(ImportError).where(ImportError.batch_id == batch.id)
    )
    assert error is not None
    assert error.error_code == "invalid_headers"


def test_commit_rejects_file_changed_after_preview(
    client: TestClient,
    db_session: Session,
) -> None:
    _, headers = authenticate(client, db_session)
    preview = client.post(
        "/api/v1/imports/product-categories/preview",
        files=upload(VALID_CSV),
        headers=headers,
    ).json()
    changed_csv = VALID_CSV.replace(b"health_beauty", b"beauty")

    response = client.post(
        f"/api/v1/imports/product-categories/{preview['batch_id']}/commit",
        files=upload(changed_csv),
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMPORT_FILE_CHANGED"
    assert db_session.scalar(select(ProductCategory)) is None


def test_manager_cannot_preview_import(
    client: TestClient,
    db_session: Session,
) -> None:
    _, headers = authenticate(client, db_session, UserRole.MANAGER)

    response = client.post(
        "/api/v1/imports/product-categories/preview",
        files=upload(VALID_CSV),
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
