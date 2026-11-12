from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
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


def seed_valid_dataset(db_session: Session) -> str:
    user = User(
        email="quality@example.com",
        password_hash="test-password-hash",
        role=UserRole.ANALYST.value,
    )
    customer = Customer(
        customer_id="customer-quality",
        customer_unique_id="person-quality",
        customer_zip_code_prefix=10000,
        customer_city="sao paulo",
        customer_state="SP",
    )
    seller = Seller(
        seller_id="seller-quality",
        seller_zip_code_prefix=13000,
        seller_city="campinas",
        seller_state="SP",
    )
    category = ProductCategory(
        category_name="beleza_saude",
        category_name_english="health_beauty",
    )
    product = Product(
        product_id="product-quality",
        product_category_name=category.category_name,
        product_weight_g=500,
        product_length_cm=20,
        product_height_cm=10,
        product_width_cm=15,
    )
    order = Order(
        order_id="order-quality",
        customer_id=customer.customer_id,
        order_status="delivered",
        order_purchase_timestamp=datetime(2018, 1, 1, 10),
        order_approved_at=datetime(2018, 1, 1, 11),
        order_delivered_carrier_date=datetime(2018, 1, 2, 10),
        order_delivered_customer_date=datetime(2018, 1, 5, 10),
        order_estimated_delivery_date=datetime(2018, 1, 7, 10),
    )
    item = OrderItem(
        order_id=order.order_id,
        order_item_id=1,
        product_id=product.product_id,
        seller_id=seller.seller_id,
        shipping_limit_date=datetime(2018, 1, 3),
        price=Decimal("100.00"),
        freight_value=Decimal("10.00"),
    )
    payment = OrderPayment(
        order_id=order.order_id,
        payment_sequential=1,
        payment_type="credit_card",
        payment_installments=1,
        payment_value=Decimal("110.00"),
    )
    review = OrderReview(
        review_id="review-quality",
        order_id=order.order_id,
        review_score=5,
        review_creation_date=datetime(2018, 1, 6),
        review_answer_timestamp=datetime(2018, 1, 6, 12),
    )
    geolocation = Geolocation(
        geolocation_zip_code_prefix=10000,
        geolocation_lat=-23.55,
        geolocation_lng=-46.63,
        geolocation_city="sao paulo",
        geolocation_state="SP",
    )
    db_session.add_all(
        [
            user,
            customer,
            seller,
            category,
            product,
            order,
            item,
            payment,
            review,
            geolocation,
        ]
    )
    db_session.commit()
    return create_access_token(user.id, user.role)


def test_quality_report_passes_for_a_consistent_dataset(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_valid_dataset(db_session)

    response = client.get(
        "/api/v1/datasets/quality",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "passed"
    assert body["summary"] == {"passed": 33, "warnings": 0, "failed": 0}
    assert {item["table"]: item["rows"] for item in body["tables"]} == {
        "customers": 1,
        "sellers": 1,
        "product_categories": 1,
        "products": 1,
        "orders": 1,
        "order_items": 1,
        "order_payments": 1,
        "order_reviews": 1,
        "geolocations": 1,
    }
    assert body["reconciliation"] == {
        "item_value": 100.0,
        "freight_value": 10.0,
        "expected_payment_value": 110.0,
        "payment_value": 110.0,
        "difference": 0.0,
        "mismatched_orders": 0,
    }
    assert body["ml_eligibility"] == {
        "policy_version": "olist-ml-quality-v1",
        "ready_for_daily_sales": True,
        "delivered_orders": 1,
        "eligible_orders": 1,
        "excluded_orders": 0,
        "excluded_item_rows": 0,
        "excluded_revenue": 0.0,
        "delivery_feature_excluded_orders": 0,
        "unknown_category_products": 0,
    }


def test_quality_report_marks_blocking_issues_as_failed(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_valid_dataset(db_session)
    db_session.add(
        Order(
            order_id="broken-delivery",
            customer_id="customer-quality",
            order_status="delivered",
            order_purchase_timestamp=datetime(2018, 2, 1, 10),
            order_estimated_delivery_date=datetime(2018, 2, 7, 10),
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/datasets/quality",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    checks = {check["code"]: check for check in body["checks"]}
    assert body["status"] == "failed"
    assert checks["delivered_without_delivery_date"]["affected_rows"] == 1
    assert checks["delivered_without_items"]["affected_rows"] == 1
    assert checks["orders_without_payments"]["affected_rows"] == 1
    assert body["ml_eligibility"]["delivered_orders"] == 2
    assert body["ml_eligibility"]["eligible_orders"] == 1
    assert body["ml_eligibility"]["excluded_orders"] == 1
    assert body["ml_eligibility"]["ready_for_daily_sales"] is True


def test_quality_report_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/quality")

    assert response.status_code == 401
