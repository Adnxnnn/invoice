"""
tests/test_auth.py – Integration tests for InvoicePro.

All invoice-creation tests pass items_json to match the updated multi-item form.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from invoicepro.database.database import db
from invoicepro.database.models import Customer, Invoice, Payment, Product, User


# ── Helpers ──────────────────────────────────────────────────────────────────

def _items_json(item_name, price, qty=1, discount=0, gst_rate=0):
    """Build the items_json payload the invoice form expects."""
    return json.dumps([{
        "item_name": item_name,
        "description": "",
        "hsn_sac": "",
        "product_id": None,
        "unit_price": float(price),
        "quantity": float(qty),
        "discount": float(discount),
        "gst_rate": float(gst_rate),
    }])


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_register_creates_user_and_company_settings(client, app):
    response = client.post(
        "/auth/register",
        data={
            "name": "Adnan",
            "email": "adnan@example.com",
            "phone": "9999999999",
            "company_name": "InvoicePro Labs",
            "address": "Kolkata",
            "website": "https://example.com",
            "invoice_prefix": "INV",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Welcome back, Adnan" in response.data

    with app.app_context():
        user = db.session.query(User).filter_by(email="adnan@example.com").one()
        assert user.company_settings.company_name == "InvoicePro Labs"
        assert user.company_settings.invoice_prefix == "INV"


def test_login_rejects_invalid_password(client, app):
    with app.app_context():
        user = User(name="Adnan", email="adnan@example.com")
        user.set_password("correct-password")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/auth/login",
        data={"email": "adnan@example.com", "password": "wrong-password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid email or password." in response.data


def test_dashboard_requires_authentication(client):
    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_customer_creation_is_user_scoped(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "owner@example.com",
            "invoice_prefix": "INV",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    response = client.post(
        "/customers/",
        data={
            "name": "Client A",
            "email": "client@example.com",
            "phone": "12345",
            "address": "Billing address",
            "notes": "Priority account",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Customer created." in response.data

    with app.app_context():
        customer = db.session.query(Customer).filter_by(email="client@example.com").one()
        assert customer.user.email == "owner@example.com"


def test_product_creation_and_dashboard_summary(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "owner2@example.com",
            "invoice_prefix": "INV",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    client.post(
        "/products/",
        data={
            "name": "Consulting",
            "description": "Monthly retainer",
            "price": "1500.00",
            "unit": "Month",
            "gst_rate": "18",
        },
        follow_redirects=True,
    )

    with app.app_context():
        user = db.session.query(User).filter_by(email="owner2@example.com").one()
        customer = Customer(user_id=user.id, name="Client B", email="b@example.com")
        invoice = Invoice(
            user_id=user.id,
            customer=customer,
            invoice_number="INV-2026-0001",
            invoice_date=date(2026, 8, 1),
            due_date=date.today() - timedelta(days=2),
            status="Overdue",
            subtotal=Decimal("1500.00"),
            taxable_amount=Decimal("1500.00"),
            total_amount=Decimal("1500.00"),
            amount_paid=Decimal("500.00"),
        )
        db.session.add_all([customer, invoice])
        db.session.commit()

    response = client.get("/dashboard/")

    assert response.status_code == 200
    assert b"INV-2026-0001" in response.data


def test_invoice_creation_uses_saved_customer_and_product(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "billing@example.com",
            "invoice_prefix": "BILL",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    client.post(
        "/customers/",
        data={
            "name": "Client C",
            "email": "clientc@example.com",
        },
        follow_redirects=True,
    )
    client.post(
        "/products/",
        data={
            "name": "Design Sprint",
            "description": "Weekly sprint",
            "price": "2000.00",
            "unit": "Week",
            "gst_rate": "0",
        },
        follow_redirects=True,
    )

    with app.app_context():
        customer = db.session.query(Customer).filter_by(email="clientc@example.com").one()

    response = client.post(
        "/invoices/",
        data={
            "customer_id": str(customer.id),
            "invoice_date": "2026-08-13",
            "due_date": "2026-08-20",
            "status": "Sent",
            "transaction_type": "intra",
            "template": "classic",
            "currency": "INR",
            "payment_terms": "Net 7",
            "notes": "Thank you",
            "items_json": _items_json("Design Sprint", 2000, qty=2, discount=250, gst_rate=0),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invoice created." in response.data
    assert b"BILL-0001" in response.data

    with app.app_context():
        invoice = db.session.query(Invoice).filter_by(invoice_number="BILL-0001").one()
        assert invoice.customer.name == "Client C"
        assert len(invoice.items) == 1
        assert invoice.items[0].item_name == "Design Sprint"
        assert invoice.subtotal == Decimal("4000.00")
        assert invoice.discount_total == Decimal("250.00")
        assert invoice.taxable_amount == Decimal("3750.00")
        assert invoice.total_amount == Decimal("3750.00")
        assert invoice.status == "Sent"


def test_invoice_page_requires_customer_and_product_seed_data(client):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "empty@example.com",
            "invoice_prefix": "INV",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    response = client.get("/invoices/")

    assert response.status_code == 200
    assert b"Customers and products required" in response.data


def test_invoice_detail_status_workflow_and_download(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "workflow@example.com",
            "company_name": "Studio North",
            "invoice_prefix": "SN",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    client.post(
        "/customers/",
        data={"name": "Client D", "email": "d@example.com"},
        follow_redirects=True,
    )

    with app.app_context():
        customer = db.session.query(Customer).filter_by(email="d@example.com").one()

    client.post(
        "/invoices/",
        data={
            "customer_id": str(customer.id),
            "invoice_date": "2026-08-13",
            "due_date": "2026-08-18",
            "status": "Draft",
            "transaction_type": "intra",
            "template": "classic",
            "currency": "INR",
            "payment_terms": "Due on receipt",
            "notes": "Brand rollout",
            "items_json": _items_json("Brand System", 5000, gst_rate=0),
        },
        follow_redirects=True,
    )

    with app.app_context():
        invoice = db.session.query(Invoice).first()

    detail_response = client.get(f"/invoices/{invoice.id}")
    assert detail_response.status_code == 200
    assert b"Document View" in detail_response.data

    sent_response = client.post(f"/invoices/{invoice.id}/status/Sent", follow_redirects=True)
    assert sent_response.status_code == 200
    assert b"Invoice marked as Sent." in sent_response.data

    with app.app_context():
        inv = db.session.get(Invoice, invoice.id)
        assert inv.status == "Sent"

    download_response = client.get(f"/invoices/{invoice.id}/download")
    assert download_response.status_code == 200
    assert "SN-0001.html" in download_response.headers["Content-Disposition"]


def test_invoice_payment_updates_balance_and_status(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "payments@example.com",
            "invoice_prefix": "PAY",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    client.post(
        "/customers/",
        data={"name": "Client E", "email": "e@example.com"},
        follow_redirects=True,
    )

    with app.app_context():
        customer = db.session.query(Customer).filter_by(email="e@example.com").one()

    client.post(
        "/invoices/",
        data={
            "customer_id": str(customer.id),
            "invoice_date": "2026-08-10",
            "due_date": "2026-08-25",
            "status": "Pending",
            "transaction_type": "intra",
            "template": "classic",
            "currency": "INR",
            "payment_terms": "Net 15",
            "notes": "Milestone billing",
            "items_json": _items_json("Discovery", 3000, discount=500, gst_rate=0),
        },
        follow_redirects=True,
    )

    with app.app_context():
        invoice = db.session.query(Invoice).first()

    response = client.post(
        f"/invoices/{invoice.id}/payments",
        data={
            "payment_date": "2026-08-13",
            "payment_method": "Bank transfer",
            "reference_number": "UTR12345",
            "amount": "1200.00",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Payment recorded." in response.data
    assert b"UTR12345" in response.data

    with app.app_context():
        inv = db.session.query(Invoice).first()
        payment = db.session.query(Payment).filter_by(invoice_id=inv.id).one()
        assert payment.amount == Decimal("1200.00")
        assert inv.amount_paid == Decimal("1200.00")
        assert inv.balance_due == Decimal("1300.00")
        assert inv.status == "Pending"


def test_invoice_payment_rejects_overpayment(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "overpay@example.com",
            "invoice_prefix": "OVR",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    client.post(
        "/customers/",
        data={"name": "Client F", "email": "f@example.com"},
        follow_redirects=True,
    )

    with app.app_context():
        customer = db.session.query(Customer).filter_by(email="f@example.com").one()

    client.post(
        "/invoices/",
        data={
            "customer_id": str(customer.id),
            "invoice_date": "2026-08-10",
            "due_date": "2026-08-20",
            "status": "Pending",
            "transaction_type": "intra",
            "template": "classic",
            "currency": "INR",
            "payment_terms": "Net 10",
            "notes": "",
            "items_json": _items_json("Workshop", 1000, gst_rate=0),
        },
        follow_redirects=True,
    )

    with app.app_context():
        invoice = db.session.query(Invoice).first()

    response = client.post(
        f"/invoices/{invoice.id}/payments",
        data={
            "payment_date": "2026-08-13",
            "payment_method": "Cash",
            "reference_number": "RCPT-1",
            "amount": "1200.00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert b"Payment cannot exceed the remaining balance." in response.data


def test_company_settings_update_changes_profile_data(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "settings@example.com",
            "company_name": "Old Name",
            "invoice_prefix": "OLD",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )

    response = client.post(
        "/settings/",
        data={
            "company_name": "New Name Studio",
            "address": "42 Market Street",
            "website": "https://new.example.com",
            "invoice_prefix": "NEW",
            "tax_information": "Payable within 7 days",
            "default_currency": "INR",
            "default_tax_rate": "18",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Company settings updated." in response.data

    with app.app_context():
        user = db.session.query(User).filter_by(email="settings@example.com").one()
        assert user.company_settings.company_name == "New Name Studio"
        assert user.company_settings.invoice_prefix == "NEW"
        assert user.company_settings.tax_information == "Payable within 7 days"


def test_customer_edit_and_delete_flow(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "crud@example.com",
            "invoice_prefix": "CRUD",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    client.post(
        "/customers/",
        data={"name": "Client G", "email": "g@example.com", "phone": "111"},
        follow_redirects=True,
    )

    with app.app_context():
        customer = db.session.query(Customer).first()

    edit_response = client.post(
        f"/customers/{customer.id}/edit",
        data={
            "name": "Client G Updated",
            "email": "g@example.com",
            "phone": "222",
            "address": "New address",
            "notes": "VIP",
        },
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert b"Customer updated." in edit_response.data

    delete_response = client.post(f"/customers/{customer.id}/delete", follow_redirects=True)
    assert delete_response.status_code == 200
    assert b"Customer deleted." in delete_response.data

    with app.app_context():
        assert db.session.query(Customer).count() == 0


def test_product_edit_archive_and_invoice_filtering(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "filters@example.com",
            "invoice_prefix": "FLT",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    client.post(
        "/customers/",
        data={"name": "Client H", "email": "h@example.com"},
        follow_redirects=True,
    )
    client.post(
        "/products/",
        data={"name": "Audit", "price": "800.00", "unit": "Session", "gst_rate": "18"},
        follow_redirects=True,
    )

    with app.app_context():
        product = db.session.query(Product).first()

    client.post(
        f"/products/{product.id}/edit",
        data={"name": "Audit Plus", "description": "Deep review", "price": "950.00", "unit": "Session", "gst_rate": "18"},
        follow_redirects=True,
    )
    archive_response = client.post(f"/products/{product.id}/archive", follow_redirects=True)
    assert archive_response.status_code == 200
    assert b"Product archived." in archive_response.data

    with app.app_context():
        p = db.session.get(Product, product.id)
        assert p.name == "Audit Plus"
        assert p.is_active is False
        p.is_active = True
        db.session.commit()

    with app.app_context():
        customer = db.session.query(Customer).first()

    client.post(
        "/invoices/",
        data={
            "customer_id": str(customer.id),
            "invoice_date": "2026-08-13",
            "due_date": "2026-08-20",
            "status": "Sent",
            "transaction_type": "intra",
            "template": "classic",
            "currency": "INR",
            "payment_terms": "Net 7",
            "notes": "First invoice",
            "items_json": _items_json("Audit Plus", 950, gst_rate=18),
        },
        follow_redirects=True,
    )

    client.post(f"/products/{product.id}/archive", follow_redirects=True)

    response = client.get("/invoices/?q=Client%20H&status=Sent")
    assert response.status_code == 200
    assert b"FLT-0001" in response.data


def test_invoice_duplication_creates_new_draft_invoice(client, app):
    client.post(
        "/auth/register",
        data={
            "name": "Owner",
            "email": "duplicate@example.com",
            "invoice_prefix": "DUP",
            "password": "password123",
            "confirm_password": "password123",
        },
        follow_redirects=True,
    )
    client.post(
        "/customers/",
        data={"name": "Client I", "email": "i@example.com"},
        follow_redirects=True,
    )

    with app.app_context():
        customer = db.session.query(Customer).first()

    client.post(
        "/invoices/",
        data={
            "customer_id": str(customer.id),
            "invoice_date": "2026-08-12",
            "due_date": "2026-08-19",
            "status": "Sent",
            "transaction_type": "intra",
            "template": "classic",
            "currency": "INR",
            "payment_terms": "Net 7",
            "notes": "Recurring work",
            "items_json": _items_json("Retainer", 2200, discount=200, gst_rate=0),
        },
        follow_redirects=True,
    )

    with app.app_context():
        invoice = db.session.query(Invoice).first()

    response = client.post(f"/invoices/{invoice.id}/duplicate", follow_redirects=True)
    assert response.status_code == 200
    assert b"Invoice duplicated as DUP-0002." in response.data

    with app.app_context():
        invoices = db.session.query(Invoice).order_by(Invoice.id.asc()).all()
        assert len(invoices) == 2
        assert invoices[1].invoice_number == "DUP-0002"
        assert invoices[1].status == "Draft"
        assert invoices[1].total_amount == invoices[0].total_amount
