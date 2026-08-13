from datetime import UTC, date, datetime
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash

from invoicepro.database.database import db
from invoicepro.extensions import login_manager


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=datetime.utcnow,
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)

    company_settings = db.relationship(
        "CompanySettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    customers = db.relationship("Customer", back_populates="user", cascade="all, delete-orphan")
    products = db.relationship("Product", back_populates="user", cascade="all, delete-orphan")
    invoices = db.relationship("Invoice", back_populates="user", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_account


class CompanySettings(TimestampMixin, db.Model):
    __tablename__ = "company_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    company_name = db.Column(db.String(255))
    company_logo = db.Column(db.String(255))
    address = db.Column(db.Text)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(255))
    gstin = db.Column(db.String(30))
    website = db.Column(db.String(255))
    tax_information = db.Column(db.Text)
    invoice_prefix = db.Column(db.String(20), nullable=False, default="INV")
    signature = db.Column(db.String(255))
    default_currency = db.Column(db.String(10), nullable=False, default="INR")
    default_tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=18)
    payment_instructions = db.Column(db.Text)
    footer_text = db.Column(db.Text)

    user = db.relationship("User", back_populates="company_settings")


class Customer(TimestampMixin, db.Model):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_customer_user_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    address = db.Column(db.Text)
    shipping_address = db.Column(db.Text)
    gstin = db.Column(db.String(30))
    notes = db.Column(db.Text)

    user = db.relationship("User", back_populates="customers")
    invoices = db.relationship("Invoice", back_populates="customer")

    @property
    def total_billed(self):
        return sum(Decimal(inv.total_amount or 0) for inv in self.invoices)

    @property
    def total_paid(self):
        return sum(Decimal(inv.amount_paid or 0) for inv in self.invoices)

    @property
    def total_outstanding(self):
        return self.total_billed - self.total_paid


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_product_user_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    hsn_sac = db.Column(db.String(50))
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    gst_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    unit = db.Column(db.String(30), nullable=False, default="Nos")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", back_populates="products")
    invoice_items = db.relationship("InvoiceItem", back_populates="product")


import uuid


def _generate_share_token():
    return uuid.uuid4().hex


class Invoice(TimestampMixin, db.Model):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("user_id", "invoice_number", name="uq_invoice_user_number"),
        CheckConstraint(
            "status IN ('Draft', 'Sent', 'Paid', 'Pending', 'Overdue', 'Cancelled')",
            name="ck_invoice_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Draft")
    payment_terms = db.Column(db.String(255))
    currency = db.Column(db.String(10), nullable=False, default="INR")
    notes = db.Column(db.Text)
    # GST transaction type: 'intra' (CGST+SGST) or 'inter' (IGST)
    transaction_type = db.Column(db.String(10), nullable=False, default="intra")
    template = db.Column(db.String(20), nullable=False, default="classic")
    email_sent_at = db.Column(db.DateTime)
    share_token = db.Column(db.String(64), unique=True, index=True, default=_generate_share_token)
    payment_link = db.Column(db.String(500))
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount_total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    taxable_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    sgst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    igst_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    user = db.relationship("User", back_populates="invoices")
    customer = db.relationship("Customer", back_populates="invoices")
    items = db.relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def balance_due(self):
        return Decimal(self.total_amount or 0) - Decimal(self.amount_paid or 0)

    def refresh_payment_state(self):
        paid = sum(Decimal(payment.amount or 0) for payment in self.payments)
        self.amount_paid = paid
        if self.status == "Cancelled":
            return
        if paid >= Decimal(self.total_amount or 0) and Decimal(self.total_amount or 0) > 0:
            self.status = "Paid"
        elif self.due_date < datetime.now(UTC).date() and paid < Decimal(self.total_amount or 0):
            self.status = "Overdue"
        elif self.status in {"Draft", "Sent"}:
            return
        elif paid > 0 or Decimal(self.total_amount or 0) > 0:
            self.status = "Pending"


class InvoiceItem(TimestampMixin, db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), index=True)
    item_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    hsn_sac = db.Column(db.String(50))
    quantity = db.Column(db.Numeric(12, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    discount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    gst_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    line_total = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    invoice = db.relationship("Invoice", back_populates="items")
    product = db.relationship("Product", back_populates="invoice_items")


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    payment_method = db.Column(db.String(50))
    reference_number = db.Column(db.String(100))
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    user = db.relationship("User", back_populates="payments")
    invoice = db.relationship("Invoice", back_populates="payments")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
