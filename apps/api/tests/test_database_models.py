from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Customer,
    ImportBatch,
    ImportError,
    ImportStatus,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    Seller,
    User,
    UserRole,
)


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


def test_olist_sales_relationships_are_persisted(db_session: Session) -> None:
    category = ProductCategory(
        category_name="beleza_saude",
        category_name_english="health_beauty",
    )
    customer = Customer(
        customer_id="customer-1",
        customer_unique_id="person-1",
        customer_zip_code_prefix=14409,
        customer_city="franca",
        customer_state="SP",
    )
    seller = Seller(
        seller_id="seller-1",
        seller_zip_code_prefix=13023,
        seller_city="campinas",
        seller_state="SP",
    )
    product = Product(
        product_id="product-1",
        product_category_name=category.category_name,
        product_weight_g=500,
    )
    order = Order(
        order_id="order-1",
        customer_id=customer.customer_id,
        order_status="delivered",
        order_purchase_timestamp=datetime(2018, 1, 1, 10, 0),
        order_estimated_delivery_date=datetime(2018, 1, 10, 0, 0),
    )
    item = OrderItem(
        order_id=order.order_id,
        order_item_id=1,
        product_id=product.product_id,
        seller_id=seller.seller_id,
        shipping_limit_date=datetime(2018, 1, 3, 0, 0),
        price=Decimal("99.90"),
        freight_value=Decimal("10.00"),
    )
    db_session.add_all([category, customer, seller, product, order, item])
    db_session.commit()

    assert item.order.customer.customer_unique_id == "person-1"
    assert item.product.category.category_name_english == "health_beauty"
    assert item.seller.seller_state == "SP"


def test_order_rejects_unknown_status(db_session: Session) -> None:
    customer = Customer(
        customer_id="customer-2",
        customer_unique_id="person-2",
        customer_zip_code_prefix=20000,
        customer_city="rio de janeiro",
        customer_state="RJ",
    )
    db_session.add(customer)
    db_session.flush()
    db_session.add(
        Order(
            order_id="order-2",
            customer_id=customer.customer_id,
            order_status="unknown",
            order_purchase_timestamp=datetime(2018, 1, 1),
            order_estimated_delivery_date=datetime(2018, 1, 10),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_import_batch_keeps_row_errors(db_session: Session) -> None:
    user = build_user("analyst@example.com")
    db_session.add(user)
    db_session.flush()
    batch = ImportBatch(
        dataset_type="orders",
        original_filename="olist_orders_dataset.csv",
        file_checksum_sha256="a" * 64,
        status=ImportStatus.FAILED.value,
        total_rows=1,
        rejected_rows=1,
        uploaded_by_id=user.id,
        errors=[
            ImportError(
                row_number=2,
                field_name="order_status",
                error_code="invalid_value",
                error_message="Unsupported order status",
                raw_data={"order_status": "unknown"},
            )
        ],
    )
    db_session.add(batch)
    db_session.commit()

    assert batch.errors[0].row_number == 2
    assert batch.errors[0].raw_data == {"order_status": "unknown"}
