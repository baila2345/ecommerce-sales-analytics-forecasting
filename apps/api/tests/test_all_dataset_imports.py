from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    Customer,
    Geolocation,
    Order,
    OrderItem,
    OrderPayment,
    OrderReview,
    Product,
    ProductCategory,
    Seller,
    User,
    UserRole,
)


TEST_PASSWORD = "valid-test-password"
CSV_BY_SLUG = {
    "customers": (
        "customer_id,customer_unique_id,customer_zip_code_prefix,"
        "customer_city,customer_state\n"
        "customer-1,person-1,14409,franca,SP\n"
    ),
    "sellers": (
        "seller_id,seller_zip_code_prefix,seller_city,seller_state\n"
        "seller-1,13023,campinas,SP\n"
    ),
    "products": (
        "product_id,product_category_name,product_name_length,"
        "product_description_length,product_photos_qty,product_weight_g,"
        "product_length_cm,product_height_cm,product_width_cm\n"
        "product-1,new_category,12,100,2,500,20,10,15\n"
    ),
    "orders": (
        "order_id,customer_id,order_status,order_purchase_timestamp,"
        "order_approved_at,order_delivered_carrier_date,"
        "order_delivered_customer_date,order_estimated_delivery_date\n"
        "order-1,customer-1,delivered,2018-01-01 10:00:00,"
        "2018-01-01 11:00:00,2018-01-02 09:00:00,"
        "2018-01-05 12:00:00,2018-01-10 00:00:00\n"
    ),
    "order-items": (
        "order_id,order_item_id,product_id,seller_id,shipping_limit_date,"
        "price,freight_value\n"
        "order-1,1,product-1,seller-1,2018-01-03 00:00:00,99.90,10.00\n"
    ),
    "order-payments": (
        "order_id,payment_sequential,payment_type,payment_installments,"
        "payment_value\n"
        "order-1,1,credit_card,2,109.90\n"
    ),
    "order-reviews": (
        "review_id,order_id,review_score,review_comment_title,"
        "review_comment_message,review_creation_date,review_answer_timestamp\n"
        "review-1,order-1,5,Great,Excellent product,"
        "2018-01-06 00:00:00,2018-01-06 12:00:00\n"
    ),
    "geolocations": (
        "geolocation_zip_code_prefix,geolocation_lat,geolocation_lng,"
        "geolocation_city,geolocation_state\n"
        "14409,-20.5,-47.4,franca,SP\n"
    ),
}


def authenticate(client: TestClient, db_session: Session) -> dict[str, str]:
    user = User(
        email="all-imports@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.ADMIN.value,
    )
    db_session.add(user)
    db_session.commit()
    token = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def import_csv(
    client: TestClient,
    headers: dict[str, str],
    slug: str,
    content: str,
) -> None:
    file = {"file": (f"{slug}.csv", content.encode(), "text/csv")}
    preview_response = client.post(
        f"/api/v1/imports/{slug}/preview",
        files=file,
        headers=headers,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["can_import"] is True, preview["errors"]
    assert preview["total_rows"] == 1

    commit_response = client.post(
        f"/api/v1/imports/{slug}/{preview['batch_id']}/commit",
        files={"file": (f"{slug}.csv", content.encode(), "text/csv")},
        headers=headers,
    )
    assert commit_response.status_code == 200, commit_response.text
    assert commit_response.json()["imported_rows"] == 1


def test_imports_all_remaining_olist_datasets_in_dependency_order(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = authenticate(client, db_session)

    for slug, content in CSV_BY_SLUG.items():
        import_csv(client, headers, slug, content)

    model_counts = {
        Customer: 1,
        Seller: 1,
        Product: 1,
        Order: 1,
        OrderItem: 1,
        OrderPayment: 1,
        OrderReview: 1,
        Geolocation: 1,
    }
    for model, expected_count in model_counts.items():
        count = db_session.scalar(select(func.count()).select_from(model))
        assert count == expected_count
    category = db_session.get(ProductCategory, "new_category")
    assert category is not None
    assert category.category_name_english is None


def test_preview_reports_missing_foreign_key_reference(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = authenticate(client, db_session)
    response = client.post(
        "/api/v1/imports/orders/preview",
        files={"file": ("orders.csv", CSV_BY_SLUG["orders"].encode(), "text/csv")},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["can_import"] is False
    assert body["errors"][0]["code"] == "reference_not_found"
    assert body["errors"][0]["field_name"] == "customer_id"


def test_lists_all_nine_supported_datasets(
    client: TestClient,
    db_session: Session,
) -> None:
    headers = authenticate(client, db_session)

    response = client.get("/api/v1/imports/datasets", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 9
