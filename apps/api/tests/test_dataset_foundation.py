from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.models import (
    Customer,
    DailySale,
    DatasetSnapshot,
    Geolocation,
    ImportBatch,
    ImportStatus,
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
from app.modules.datasets.fingerprint import (
    REQUIRED_DATASET_TYPES,
    build_fingerprint,
)


def test_fingerprint_is_deterministic_and_includes_maturity_config() -> None:
    checksums = {
        dataset_type: f"{index:064x}"
        for index, dataset_type in enumerate(REQUIRED_DATASET_TYPES, start=1)
    }

    first = build_fingerprint(
        dict(reversed(list(checksums.items()))),
        maturity_days=30,
        source_min_date=date(2017, 1, 1),
        source_max_date=date(2018, 1, 1),
    )
    second = build_fingerprint(
        checksums,
        maturity_days=30,
        source_min_date=date(2017, 1, 1),
        source_max_date=date(2018, 1, 1),
    )
    changed = build_fingerprint(
        checksums,
        maturity_days=45,
        source_min_date=date(2017, 1, 1),
        source_max_date=date(2018, 1, 1),
    )

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != changed.fingerprint
    assert len(first.fingerprint) == 64


def seed_dataset_foundation(db_session: Session) -> str:
    user = User(
        email="dataset@example.com",
        password_hash="test-password-hash",
        role=UserRole.ANALYST.value,
    )
    customer = Customer(
        customer_id="dataset-customer",
        customer_unique_id="dataset-person",
        customer_zip_code_prefix=10000,
        customer_city="sao paulo",
        customer_state="SP",
    )
    seller = Seller(
        seller_id="dataset-seller",
        seller_zip_code_prefix=13000,
        seller_city="campinas",
        seller_state="SP",
    )
    category = ProductCategory(
        category_name="beleza_saude",
        category_name_english="health_beauty",
    )
    product = Product(
        product_id="dataset-product",
        product_category_name=category.category_name,
        product_weight_g=500,
        product_length_cm=20,
        product_height_cm=10,
        product_width_cm=15,
    )
    delivered = Order(
        order_id="dataset-delivered",
        customer_id=customer.customer_id,
        order_status="delivered",
        order_purchase_timestamp=datetime(2018, 1, 1, 10),
        order_approved_at=datetime(2018, 1, 1, 11),
        order_delivered_carrier_date=datetime(2018, 1, 2, 10),
        order_delivered_customer_date=datetime(2018, 1, 3, 10),
        order_estimated_delivery_date=datetime(2018, 1, 5, 10),
    )
    canceled = Order(
        order_id="dataset-canceled",
        customer_id=customer.customer_id,
        order_status="canceled",
        order_purchase_timestamp=datetime(2018, 1, 3, 10),
        order_estimated_delivery_date=datetime(2018, 1, 8, 10),
    )
    item = OrderItem(
        order_id=delivered.order_id,
        order_item_id=1,
        product_id=product.product_id,
        seller_id=seller.seller_id,
        shipping_limit_date=datetime(2018, 1, 2),
        price=Decimal("100.00"),
        freight_value=Decimal("10.00"),
    )
    payments = [
        OrderPayment(
            order_id=delivered.order_id,
            payment_sequential=1,
            payment_type="credit_card",
            payment_installments=1,
            payment_value=Decimal("110.00"),
        ),
        OrderPayment(
            order_id=canceled.order_id,
            payment_sequential=1,
            payment_type="voucher",
            payment_installments=1,
            payment_value=Decimal("0.00"),
        ),
    ]
    review = OrderReview(
        review_id="dataset-review",
        order_id=delivered.order_id,
        review_score=5,
        review_creation_date=datetime(2018, 1, 4),
        review_answer_timestamp=datetime(2018, 1, 4, 12),
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
            delivered,
            canceled,
            item,
            *payments,
            review,
            geolocation,
        ]
    )
    db_session.flush()
    db_session.add_all(
        ImportBatch(
            dataset_type=dataset_type,
            original_filename=f"{dataset_type}.csv",
            file_checksum_sha256=f"{index:064x}",
            status=ImportStatus.COMPLETED.value,
            total_rows=1,
            valid_rows=1,
            imported_rows=1,
            rejected_rows=0,
            uploaded_by_id=user.id,
            completed_at=datetime(2018, 1, 10),
        )
        for index, dataset_type in enumerate(REQUIRED_DATASET_TYPES, start=1)
    )
    db_session.commit()
    return create_access_token(user.id, user.role)


def test_rebuild_daily_sales_creates_an_idempotent_complete_calendar(
    client: TestClient,
    db_session: Session,
) -> None:
    token = seed_dataset_foundation(db_session)
    headers = {"Authorization": f"Bearer {token}"}

    fingerprint = client.get(
        "/api/v1/datasets/fingerprint?maturity_days=1", headers=headers
    )
    rebuilt = client.post(
        "/api/v1/datasets/daily-sales/rebuild?maturity_days=1",
        headers=headers,
    )
    rebuilt_again = client.post(
        "/api/v1/datasets/daily-sales/rebuild?maturity_days=1",
        headers=headers,
    )
    latest = client.get("/api/v1/datasets/snapshots/latest", headers=headers)

    assert fingerprint.status_code == 200
    assert rebuilt.status_code == 200
    assert rebuilt_again.status_code == 200
    assert latest.status_code == 200
    body = rebuilt.json()
    assert body["fingerprint"] == fingerprint.json()["fingerprint"]
    assert body["id"] == rebuilt_again.json()["id"] == latest.json()["id"]
    assert body["status"] == "ready"
    assert body["source_min_date"] == "2018-01-01"
    assert body["source_max_date"] == "2018-01-03"
    assert body["mature_until"] == "2018-01-01"
    assert body["daily_sales_days"] == 3
    assert body["mature_days"] == 1
    assert body["sales_value"] == 100.0
    assert body["orders_count"] == 1
    assert db_session.scalar(select(func.count()).select_from(DatasetSnapshot)) == 1

    daily_rows = list(
        db_session.scalars(select(DailySale).order_by(DailySale.sales_date))
    )
    assert [row.sales_date.isoformat() for row in daily_rows] == [
        "2018-01-01",
        "2018-01-02",
        "2018-01-03",
    ]
    assert daily_rows[0].aov == Decimal("100.00")
    assert daily_rows[1].sales_value == Decimal("0.00")
    assert daily_rows[1].orders_count == 0
    assert daily_rows[1].aov is None
    assert daily_rows[2].is_mature is False
