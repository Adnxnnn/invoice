import pytest
from invoicepro import create_app
from invoicepro.database.database import db
from invoicepro.database.models import CompanySettings, Product, User
from config import TestingConfig


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture
def new_user(app):
    with app.app_context():
        user = User(name="Test User", email="test@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        # Always create company settings so routes don't blow up
        settings = CompanySettings(user_id=user.id, invoice_prefix="TEST")
        db.session.add(settings)
        db.session.commit()
        yield user


@pytest.fixture
def new_product(app, new_user):
    with app.app_context():
        product = Product(
            user_id=new_user.id,
            name="Test Product",
            price=10.00,
            unit="pcs",
            gst_rate=18,
        )
        db.session.add(product)
        db.session.commit()
        yield product
