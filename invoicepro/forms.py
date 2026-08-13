from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    FileField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import ValidationError
from wtforms.validators import Email, EqualTo, InputRequired, Length, NumberRange, Optional


GST_RATE_CHOICES = [
    ("0", "0% – Exempt"),
    ("5", "5%"),
    ("12", "12%"),
    ("18", "18%"),
    ("28", "28%"),
]

CURRENCY_CHOICES = [
    ("INR", "INR – Indian Rupee"),
    ("USD", "USD – US Dollar"),
    ("EUR", "EUR – Euro"),
    ("GBP", "GBP – British Pound"),
    ("AED", "AED – UAE Dirham"),
]


class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[InputRequired(), Length(max=120)])
    email = StringField("Email", validators=[InputRequired(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    company_name = StringField("Company name", validators=[Optional(), Length(max=255)])
    address = TextAreaField("Company address", validators=[Optional(), Length(max=1000)])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    invoice_prefix = StringField(
        "Invoice prefix",
        validators=[InputRequired(), Length(min=2, max=20)],
        default="INV",
    )
    password = PasswordField(
        "Password",
        validators=[InputRequired(), Length(min=8, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[InputRequired(), EqualTo("password")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[InputRequired(), Length(max=128)])
    submit = SubmitField("Log in")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Email(), Length(max=255)])
    submit = SubmitField("Request reset")


class CustomerForm(FlaskForm):
    name = StringField("Customer name", validators=[InputRequired(), Length(max=255)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    address = TextAreaField("Billing address", validators=[Optional(), Length(max=1000)])
    shipping_address = TextAreaField("Shipping address", validators=[Optional(), Length(max=1000)])
    gstin = StringField("GSTIN", validators=[Optional(), Length(max=30)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Save customer")


class ProductForm(FlaskForm):
    name = StringField("Product / Service name", validators=[InputRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    hsn_sac = StringField("HSN / SAC code", validators=[Optional(), Length(max=50)])
    price = DecimalField(
        "Unit price",
        validators=[InputRequired(), NumberRange(min=0)],
        places=2,
    )
    gst_rate = SelectField(
        "GST rate",
        choices=GST_RATE_CHOICES,
        default="18",
    )
    unit = StringField("Unit", validators=[InputRequired(), Length(max=30)])
    submit = SubmitField("Save product")


class InvoiceCreateForm(FlaskForm):
    """Used for the full multi-item invoice creation page."""
    customer_id = SelectField("Customer", validators=[InputRequired()], coerce=int)
    invoice_date = DateField("Invoice date", validators=[InputRequired()], format="%Y-%m-%d")
    due_date = DateField("Due date", validators=[InputRequired()], format="%Y-%m-%d")
    status = SelectField(
        "Initial status",
        validators=[InputRequired()],
        choices=[
            ("Draft", "Draft"),
            ("Sent", "Sent"),
            ("Pending", "Pending"),
        ],
        default="Draft",
    )
    transaction_type = SelectField(
        "Transaction type",
        choices=[
            ("intra", "Intra-state (CGST + SGST)"),
            ("inter", "Inter-state (IGST)"),
        ],
        default="intra",
    )
    template = SelectField(
        "Invoice template",
        choices=[
            ("classic", "Classic"),
            ("modern", "Modern"),
            ("minimal", "Minimal"),
        ],
        default="classic",
    )
    currency = SelectField("Currency", choices=CURRENCY_CHOICES, default="INR")
    payment_terms = StringField("Payment terms", validators=[Optional(), Length(max=255)])
    payment_link = StringField("Online payment link (Razorpay/Stripe/UPI)", validators=[Optional(), Length(max=500)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    # Items are submitted as JSON via a hidden field
    items_json = HiddenField("Items JSON", validators=[InputRequired()])
    submit = SubmitField("Create invoice")

    def validate_due_date(self, field):
        if self.invoice_date.data and field.data and field.data < self.invoice_date.data:
            raise ValidationError("Due date cannot be earlier than the invoice date.")


class InvoiceEditForm(FlaskForm):
    """Simplified edit form (metadata only – items handled separately)."""
    customer_id = SelectField("Customer", validators=[InputRequired()], coerce=int)
    invoice_date = DateField("Invoice date", validators=[InputRequired()], format="%Y-%m-%d")
    due_date = DateField("Due date", validators=[InputRequired()], format="%Y-%m-%d")
    status = SelectField(
        "Status",
        validators=[InputRequired()],
        choices=[
            ("Draft", "Draft"),
            ("Sent", "Sent"),
            ("Pending", "Pending"),
            ("Paid", "Paid"),
            ("Overdue", "Overdue"),
            ("Cancelled", "Cancelled"),
        ],
    )
    transaction_type = SelectField(
        "Transaction type",
        choices=[
            ("intra", "Intra-state (CGST + SGST)"),
            ("inter", "Inter-state (IGST)"),
        ],
        default="intra",
    )
    template = SelectField(
        "Invoice template",
        choices=[
            ("classic", "Classic"),
            ("modern", "Modern"),
            ("minimal", "Minimal"),
        ],
        default="classic",
    )
    currency = SelectField("Currency", choices=CURRENCY_CHOICES, default="INR")
    payment_terms = StringField("Payment terms", validators=[Optional(), Length(max=255)])
    payment_link = StringField("Online payment link (Razorpay/Stripe/UPI)", validators=[Optional(), Length(max=500)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    items_json = HiddenField("Items JSON", validators=[InputRequired()])
    submit = SubmitField("Save changes")

    def validate_due_date(self, field):
        if self.invoice_date.data and field.data and field.data < self.invoice_date.data:
            raise ValidationError("Due date cannot be earlier than the invoice date.")


class PaymentForm(FlaskForm):
    payment_date = DateField("Payment date", validators=[InputRequired()], format="%Y-%m-%d")
    payment_method = StringField("Payment method", validators=[Optional(), Length(max=50)])
    reference_number = StringField("Reference / Transaction number", validators=[Optional(), Length(max=100)])
    amount = DecimalField(
        "Amount received",
        validators=[InputRequired(), NumberRange(min=0.01)],
        places=2,
    )
    submit = SubmitField("Record payment")


class SendEmailForm(FlaskForm):
    recipient_email = StringField("Recipient email", validators=[InputRequired(), Email(), Length(max=255)])
    subject = StringField("Subject", validators=[InputRequired(), Length(max=255)])
    body = TextAreaField("Message", validators=[InputRequired(), Length(max=4000)])
    submit = SubmitField("Send email")


class CompanySettingsForm(FlaskForm):
    company_name = StringField("Company name", validators=[Optional(), Length(max=255)])
    address = TextAreaField("Business address", validators=[Optional(), Length(max=1000)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    email = StringField("Business email", validators=[Optional(), Email(), Length(max=255)])
    gstin = StringField("GSTIN", validators=[Optional(), Length(max=30)])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    invoice_prefix = StringField(
        "Invoice prefix",
        validators=[InputRequired(), Length(min=2, max=20)],
    )
    default_currency = SelectField("Default currency", choices=CURRENCY_CHOICES, default="INR")
    default_tax_rate = SelectField(
        "Default GST rate",
        choices=GST_RATE_CHOICES,
        default="18",
    )
    payment_instructions = TextAreaField("Payment instructions", validators=[Optional(), Length(max=2000)])
    footer_text = TextAreaField("Invoice footer text", validators=[Optional(), Length(max=500)])
    tax_information = TextAreaField("Business / Tax notes", validators=[Optional(), Length(max=1000)])
    logo = FileField("Company logo (PNG/JPG/WEBP)")
    signature = FileField("Authorized signature (PNG/JPG/WEBP)")
    submit = SubmitField("Save settings")
