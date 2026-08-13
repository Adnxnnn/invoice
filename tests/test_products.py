import pytest
from invoicepro.database.database import db
from invoicepro.database.models import Product

@pytest.fixture
def product_data():
    return {
        "name": "Test Product",
        "description": "This is a test product.",
        "price": 10.00,
        "unit": "pcs",
        "gst_rate": "18",
    }

def test_product_creation(client, app, new_user, product_data):
    """GIVEN a logged-in user WHEN they create a product THEN it is saved."""
    client.post("/auth/login", data={"email": "test@example.com", "password": "password"})
    response = client.post("/products/", data=product_data, follow_redirects=True)
    assert response.status_code == 200
    assert "Product created." in response.get_data(as_text=True)
    with app.app_context():
        product = Product.query.filter_by(name="Test Product").first()
        assert product is not None

def test_product_update(client, app, new_user, new_product, product_data):
    """GIVEN an existing product WHEN the user edits it THEN it is updated."""
    client.post("/auth/login", data={"email": "test@example.com", "password": "password"})
    product_data["name"] = "Updated Product"
    response = client.post(
        f"/products/{new_product.id}/edit",
        data=product_data,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Product updated." in response.get_data(as_text=True)
    with app.app_context():
        product = db.session.get(Product, new_product.id)
        assert product.name == "Updated Product"

def test_product_archive(client, app, new_user, new_product):
    """GIVEN an active product WHEN archived THEN it becomes inactive."""
    client.post("/auth/login", data={"email": "test@example.com", "password": "password"})
    response = client.post(f"/products/{new_product.id}/archive", follow_redirects=True)
    assert response.status_code == 200
    assert "Product archived." in response.get_data(as_text=True)
    with app.app_context():
        product = db.session.get(Product, new_product.id)
        assert not product.is_active

def test_product_activate(client, app, new_user, new_product):
    """GIVEN an archived product WHEN reactivated THEN it becomes active."""
    client.post("/auth/login", data={"email": "test@example.com", "password": "password"})
    client.post(f"/products/{new_product.id}/archive", follow_redirects=True)
    response = client.post(f"/products/{new_product.id}/archive", follow_redirects=True)
    assert response.status_code == 200
    assert "Product activated." in response.get_data(as_text=True)
    with app.app_context():
        product = db.session.get(Product, new_product.id)
        assert product.is_active
