from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import (
    Customer,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    Seller,
    User,
    UserRole,
)


def seed_analytics_data(db_session: Session) -> str:
    user = User(
        email="analyst@example.com",
        password_hash="test-password-hash",
        role=UserRole.ANALYST.value,
    )
    category = ProductCategory(
        category_name="beleza_saude",
        category_name_english="health_beauty",
    )
    customers = [
        Customer(
            customer_id="customer-1",
            customer_unique_id="person-1",
            customer_zip_code_prefix=10000,
            customer_city="sao paulo",
            customer_state="SP",
        ),
        Customer(
            customer_id="customer-2",
            customer_unique_id="person-2",
            customer_zip_code_prefix=20000,
            customer_city="rio de janeiro",
            customer_state="RJ",
        ),
    ]
    seller = Seller(
        seller_id="seller-1",
        seller_zip_code_prefix=13000,
        seller_city="campinas",
        seller_state="SP",
    )
    products = [
        Product(product_id="product-1", product_category_name=category.category_name),
        Product(product_id="product-2", product_category_name=category.category_name),
    ]
    orders = [
        Order(
            order_id="order-1",
            customer_id="customer-1",
            order_status="delivered",
            order_purchase_timestamp=datetime(2018, 1, 5, 10),
            order_delivered_customer_date=datetime(2018, 1, 10, 10),
            order_estimated_delivery_date=datetime(2018, 1, 12, 10),
        ),
        Order(
            order_id="order-2",
            customer_id="customer-2",
            order_status="canceled",
            order_purchase_timestamp=datetime(2018, 2, 5, 10),
            order_estimated_delivery_date=datetime(2018, 2, 12, 10),
        ),
    ]
    items = [
        OrderItem(
            order_id="order-1",
            order_item_id=1,
            product_id="product-1",
            seller_id="seller-1",
            shipping_limit_date=datetime(2018, 1, 7),
            price=Decimal("100.00"),
            freight_value=Decimal("10.00"),
        ),
        OrderItem(
            order_id="order-1",
            order_item_id=2,
            product_id="product-2",
            seller_id="seller-1",
            shipping_limit_date=datetime(2018, 1, 7),
            price=Decimal("50.00"),
            freight_value=Decimal("5.00"),
        ),
        OrderItem(
            order_id="order-2",
            order_item_id=1,
            product_id="product-1",
            seller_id="seller-1",
            shipping_limit_date=datetime(2018, 2, 7),
            price=Decimal("999.00"),
            freight_value=Decimal("20.00"),
        ),
    ]
    db_session.add_all([user, category, *customers, seller, *products, *orders, *items])
    db_session.commit()
    return create_access_token(user.id, user.role)


def test_dashboard_returns_distinct_order_metrics(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_analytics_data(db_session)

    response = client.get(
        "/api/v1/analytics/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overview"] == {
        "revenue": 150.0,
        "orders": 1,
        "customers": 1,
        "average_order_value": 150.0,
        "items_sold": 2,
        "freight_value": 15.0,
        "delivered_rate": 50.0,
        "average_delivery_days": 5.0,
    }
    assert body["revenue_trend"] == [
        {"period": "2018-01", "revenue": 150.0, "orders": 1}
    ]
    assert body["top_categories"][0]["label"] == "health_beauty"
    assert body["delivery"][0]["on_time_rate"] == 100.0


def test_dashboard_filters_and_exports_csv(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_analytics_data(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    filtered = client.get(
        "/api/v1/analytics/dashboard?state=RJ",
        headers=headers,
    )
    options = client.get("/api/v1/analytics/filters", headers=headers)
    exported = client.get(
        "/api/v1/analytics/export?date_from=2018-01-01&date_to=2018-01-31",
        headers=headers,
    )

    assert filtered.status_code == 200
    assert filtered.json()["overview"]["revenue"] == 0
    assert filtered.json()["filters"]["state"] == "RJ"
    assert options.status_code == 200
    assert options.json()["states"] == ["RJ", "SP"]
    assert options.json()["min_date"] == "2018-01-05"
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "Revenue trend" in exported.text
    assert "2018-01,150.0,1" in exported.text


def test_dashboard_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/analytics/dashboard")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_dashboard_rejects_an_invalid_date_range(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_analytics_data(db_session)

    response = client.get(
        "/api/v1/analytics/dashboard?date_from=2018-02-01&date_to=2018-01-01",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"
