import json
import razorpay
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint, Response, abort, current_app, flash, jsonify,
    redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from invoicepro.database.database import db
from invoicepro.database.models import Customer, Invoice, InvoiceItem, Payment, Product, User
from invoicepro.forms import InvoiceCreateForm, InvoiceEditForm, PaymentForm, SendEmailForm
from invoicepro.services.gst_calculator import calculate_invoice
from invoicepro.services.pdf_generator import generate_pdf, pdf_filename
from invoicepro.services.docx_generator import generate_docx
from invoicepro.services.email_service import send_invoice_email


TWOPLACES = Decimal("0.01")
invoices_bp = Blueprint("invoices", __name__, url_prefix="/invoices")

STATUS_CHOICES = ["Draft", "Sent", "Pending", "Paid", "Overdue", "Cancelled"]
DATE_FILTERS = ["today", "week", "month", "year", "custom"]


def _q(v) -> Decimal:
    return Decimal(str(v)).quantize(TWOPLACES)


def _next_invoice_number():
    prefix = current_user.company_settings.invoice_prefix or "INV"
    latest = db.session.execute(
        select(Invoice.invoice_number)
        .where(Invoice.user_id == current_user.id)
        .order_by(Invoice.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    seq = 1
    if latest and latest.startswith(f"{prefix}-"):
        tail = latest.removeprefix(f"{prefix}-")
        if tail.isdigit():
            seq = int(tail) + 1
    return f"{prefix}-{seq:04d}"


def _get_owned_invoice(invoice_id):
    inv = db.session.get(Invoice, invoice_id)
    if not inv or inv.user_id != current_user.id:
        abort(404)
    return inv


def _parse_items_json(raw: str) -> list[dict]:
    """Parse the items JSON submitted from the invoice form."""
    try:
        items = json.loads(raw)
        if not isinstance(items, list) or not items:
            raise ValueError("At least one item is required.")
        parsed = []
        for item in items:
            parsed.append({
                "item_name": str(item.get("item_name", "")).strip(),
                "description": str(item.get("description", "")).strip(),
                "hsn_sac": str(item.get("hsn_sac", "")).strip(),
                "product_id": int(item["product_id"]) if item.get("product_id") else None,
                "unit_price": _q(item.get("unit_price", 0)),
                "quantity": _q(item.get("quantity", 1)),
                "discount": _q(item.get("discount", 0)),
                "gst_rate": _q(item.get("gst_rate", 0)),
            })
            if not parsed[-1]["item_name"]:
                raise ValueError("Each item must have a name.")
        return parsed
    except (ValueError, KeyError, InvalidOperation) as exc:
        raise ValueError(f"Invalid items data: {exc}") from exc


def _build_invoice_items(invoice, parsed_items, transaction_type):
    """Calculate GST and create InvoiceItem objects."""
    calc = calculate_invoice(
        [
            {
                "unit_price": item["unit_price"],
                "quantity": item["quantity"],
                "discount": item["discount"],
                "gst_rate": item["gst_rate"],
            }
            for item in parsed_items
        ],
        transaction_type=transaction_type,
    )
    for item_data, calc_item in zip(parsed_items, calc["items"]):
        invoice.items.append(InvoiceItem(
            product_id=item_data["product_id"],
            item_name=item_data["item_name"],
            description=item_data["description"] or None,
            hsn_sac=item_data["hsn_sac"] or None,
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            discount=item_data["discount"],
            gst_rate=item_data["gst_rate"],
            tax_amount=calc_item["tax_amount"],
            line_total=calc_item["line_total"],
        ))
    return calc


def _apply_date_filter(q, period, date_from_str=None, date_to_str=None):
    today = date.today()
    if period == "today":
        return q.filter(Invoice.invoice_date == today)
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return q.filter(Invoice.invoice_date >= start)
    if period == "month":
        return q.filter(Invoice.invoice_date >= today.replace(day=1))
    if period == "year":
        return q.filter(Invoice.invoice_date >= today.replace(month=1, day=1))
    if period == "custom" and date_from_str and date_to_str:
        try:
            df = date.fromisoformat(date_from_str)
            dt = date.fromisoformat(date_to_str)
            return q.filter(Invoice.invoice_date >= df, Invoice.invoice_date <= dt)
        except ValueError:
            pass
    return q


# ─── Product JSON API ────────────────────────────────────────────────────────

@invoices_bp.get("/api/products")
@login_required
def api_products():
    """Return active products as JSON for JS autocomplete in invoice form."""
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).all()
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "description": p.description or "",
            "hsn_sac": p.hsn_sac or "",
            "price": float(p.price),
            "gst_rate": float(p.gst_rate),
            "unit": p.unit,
        }
        for p in products
    ])


# ─── Invoice List + Create ───────────────────────────────────────────────────

@invoices_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    query_text = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    date_filter = (request.args.get("date_filter") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()

    customers = Customer.query.filter_by(user_id=current_user.id).order_by(Customer.name).all()
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()

    form = InvoiceCreateForm(
        invoice_date=date.today(),
        due_date=date.today() + timedelta(days=7),
        status="Draft",
    )
    form.customer_id.choices = [(c.id, c.name) for c in customers]

    if form.validate_on_submit():
        try:
            parsed_items = _parse_items_json(form.items_json.data)
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            customer = db.session.get(Customer, form.customer_id.data)
            if not customer or customer.user_id != current_user.id:
                flash("Invalid customer.", "danger")
            else:
                invoice = Invoice(
                    user_id=current_user.id,
                    customer_id=customer.id,
                    invoice_number=_next_invoice_number(),
                    invoice_date=form.invoice_date.data,
                    due_date=form.due_date.data,
                    status=form.status.data,
                    transaction_type=form.transaction_type.data,
                    template=form.template.data,
                    currency=form.currency.data,
                    payment_terms=(form.payment_terms.data or "").strip() or None,
                    payment_link=(form.payment_link.data or "").strip() or None,
                    notes=(form.notes.data or "").strip() or None,
                )
                calc = _build_invoice_items(invoice, parsed_items, form.transaction_type.data)
                invoice.subtotal = calc["subtotal"]
                invoice.discount_total = calc["discount_total"]
                invoice.taxable_amount = calc["taxable_amount"]
                invoice.cgst_amount = calc["cgst_amount"]
                invoice.sgst_amount = calc["sgst_amount"]
                invoice.igst_amount = calc["igst_amount"]
                invoice.total_amount = calc["total_amount"]
                invoice.amount_paid = Decimal("0.00")
                db.session.add(invoice)
                db.session.commit()
                flash("Invoice created.", "success")
                return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    invoices_q = Invoice.query.filter_by(user_id=current_user.id)
    if status_filter:
        invoices_q = invoices_q.filter(Invoice.status == status_filter)
    if query_text:
        invoices_q = invoices_q.join(Customer).filter(
            or_(
                Invoice.invoice_number.ilike(f"%{query_text}%"),
                Customer.name.ilike(f"%{query_text}%"),
            )
        )
    if date_filter:
        invoices_q = _apply_date_filter(invoices_q, date_filter, date_from, date_to)
    invoices = invoices_q.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).all()

    # Ensure all existing invoices have a share_token
    import uuid
    dirty = False
    for inv in invoices:
        if not inv.share_token:
            inv.share_token = uuid.uuid4().hex
            dirty = True
    if dirty:
        db.session.commit()

    return render_template(
        "invoices/index.html",
        form=form,
        invoices=invoices,
        customers=customers,
        products=products,
        has_dependencies=bool(customers and products),
        query_text=query_text,
        status_filter=status_filter,
        date_filter=date_filter,
        date_from=date_from,
        date_to=date_to,
        status_choices=STATUS_CHOICES,
        date_filter_choices=DATE_FILTERS,
    )


# ─── Public Unauthenticated Invoice View & Payment Confirmation ──────────────

@invoices_bp.get("/public/<token>")
def public_view(token):
    from sqlalchemy.orm import joinedload
    invoice = Invoice.query.options(
        joinedload(Invoice.customer),
        joinedload(Invoice.user).joinedload(User.company_settings),
        joinedload(Invoice.items)
    ).filter_by(share_token=token).first_or_404()
    invoice.refresh_payment_state()
    db.session.commit()
    tmpl = invoice.template if invoice.template in {"classic", "modern", "minimal"} else "classic"
    return render_template("invoices/public_view.html", invoice=invoice, template_name=tmpl)


from invoicepro.extensions import csrf


@invoices_bp.post("/public/<token>/confirm-payment")
@csrf.exempt
def public_confirm_payment(token):
    invoice = Invoice.query.filter_by(share_token=token).first_or_404()
    if invoice.status != "Paid":
        amount_due = invoice.balance_due if invoice.balance_due > 0 else invoice.total_amount
        payment = Payment(
            invoice_id=invoice.id,
            user_id=invoice.user_id,
            payment_date=date.today(),
            amount=amount_due,
            payment_method=request.form.get("method", "Online Payment").strip(),
            reference_number=request.form.get("reference", f"ONLINE-{token[:8].upper()}").strip(),
        )
        db.session.add(payment)
        invoice.amount_paid = Decimal(invoice.amount_paid or 0) + Decimal(amount_due)
        invoice.status = "Paid"
        db.session.commit()
        flash("🎉 Payment confirmed! Thank you for your payment.", "success")
    return redirect(url_for("invoices.public_view", token=token))


# ─── Batch ZIP PDF Export ───────────────────────────────────────────────────

@invoices_bp.get("/export/zip")
@login_required
def export_zip():
    import io
    import zipfile

    invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(Invoice.id.desc()).all()
    if not invoices:
        flash("No invoices available to export.", "warning")
        return redirect(url_for("invoices.index"))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            content, mimetype = generate_pdf(inv)
            ext = ".pdf" if mimetype == "application/pdf" else ".html"
            zf.writestr(f"{inv.invoice_number}{ext}", content)

    buf.seek(0)
    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": 'attachment; filename="InvoicePro_All_Invoices.zip"'},
    )


# ─── Invoice Detail ──────────────────────────────────────────────────────────

@invoices_bp.get("/<int:invoice_id>")
@login_required
def detail(invoice_id):
    import uuid
    invoice = _get_owned_invoice(invoice_id)
    if not invoice.share_token:
        invoice.share_token = uuid.uuid4().hex
    invoice.refresh_payment_state()
    db.session.commit()
    payment_form = PaymentForm(
        payment_date=date.today(),
        amount=invoice.balance_due if invoice.balance_due > 0 else Decimal("0.00"),
    )
    email_form = SendEmailForm(
        recipient_email=invoice.customer.email or "",
        subject=f"Invoice {invoice.invoice_number} from {invoice.user.company_settings.company_name or invoice.user.name}",
        body=f"Dear {invoice.customer.name},\n\nPlease find attached invoice {invoice.invoice_number} for {invoice.currency} {invoice.total_amount}.\n\nDue date: {invoice.due_date.strftime('%d %b %Y')}\n\nView online: {url_for('invoices.public_view', token=invoice.share_token, _external=True)}\n\nThank you for your business.\n\n{invoice.user.name}",
    )
    return render_template(
        "invoices/detail.html",
        invoice=invoice,
        payment_form=payment_form,
        email_form=email_form,
    )


# ─── Invoice Edit ────────────────────────────────────────────────────────────

@invoices_bp.route("/<int:invoice_id>/edit", methods=["GET", "POST"])
@login_required
def edit(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    customers = Customer.query.filter_by(user_id=current_user.id).order_by(Customer.name).all()
    products = Product.query.filter_by(user_id=current_user.id, is_active=True).order_by(Product.name).all()

    form = InvoiceEditForm(obj=invoice)
    form.customer_id.choices = [(c.id, c.name) for c in customers]

    if form.validate_on_submit():
        try:
            parsed_items = _parse_items_json(form.items_json.data)
        except ValueError as exc:
            flash(str(exc), "danger")
        else:
            customer = db.session.get(Customer, form.customer_id.data)
            if not customer or customer.user_id != current_user.id:
                flash("Invalid customer.", "danger")
            else:
                invoice.customer_id = customer.id
                invoice.invoice_date = form.invoice_date.data
                invoice.due_date = form.due_date.data
                invoice.status = form.status.data
                invoice.transaction_type = form.transaction_type.data
                invoice.template = form.template.data
                invoice.currency = form.currency.data
                invoice.payment_terms = (form.payment_terms.data or "").strip() or None
                invoice.payment_link = (form.payment_link.data or "").strip() or None
                invoice.notes = (form.notes.data or "").strip() or None

                # Replace items
                for item in list(invoice.items):
                    db.session.delete(item)
                db.session.flush()
                calc = _build_invoice_items(invoice, parsed_items, form.transaction_type.data)
                invoice.subtotal = calc["subtotal"]
                invoice.discount_total = calc["discount_total"]
                invoice.taxable_amount = calc["taxable_amount"]
                invoice.cgst_amount = calc["cgst_amount"]
                invoice.sgst_amount = calc["sgst_amount"]
                invoice.igst_amount = calc["igst_amount"]
                invoice.total_amount = calc["total_amount"]
                invoice.refresh_payment_state()
                db.session.commit()
                flash("Invoice updated.", "success")
                return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    # Pre-populate items JSON for the form
    existing_items = [
        {
            "item_name": item.item_name,
            "description": item.description or "",
            "hsn_sac": item.hsn_sac or "",
            "product_id": item.product_id,
            "unit_price": float(item.unit_price),
            "quantity": float(item.quantity),
            "discount": float(item.discount),
            "gst_rate": float(item.gst_rate),
        }
        for item in invoice.items
    ]

    return render_template(
        "invoices/edit.html",
        form=form,
        invoice=invoice,
        customers=customers,
        products=products,
        existing_items_json=json.dumps(existing_items),
    )


# ─── Invoice Delete ──────────────────────────────────────────────────────────

@invoices_bp.post("/<int:invoice_id>/delete")
@login_required
def delete(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices.index"))


# ─── Status Update ───────────────────────────────────────────────────────────

@invoices_bp.post("/<int:invoice_id>/status/<status>")
@login_required
def update_status(invoice_id, status):
    invoice = _get_owned_invoice(invoice_id)
    allowed = {"Draft", "Sent", "Pending", "Paid", "Cancelled"}
    if status not in allowed:
        abort(404)
    invoice.status = status
    invoice.refresh_payment_state()
    if status == "Cancelled":
        invoice.status = "Cancelled"
    elif status == "Paid":
        invoice.amount_paid = invoice.total_amount
        invoice.status = "Paid"
    db.session.commit()
    flash(f"Invoice marked as {invoice.status}.", "success")
    return redirect(url_for("invoices.detail", invoice_id=invoice.id))


# ─── Payments ────────────────────────────────────────────────────────────────

@invoices_bp.post("/<int:invoice_id>/payments")
@login_required
def add_payment(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    payment_form = PaymentForm()
    invoice.refresh_payment_state()

    if payment_form.validate_on_submit():
        amount = _q(payment_form.amount.data)
        if invoice.status == "Cancelled":
            payment_form.amount.errors.append("Cancelled invoices cannot receive payments.")
        elif amount > invoice.balance_due:
            payment_form.amount.errors.append("Payment cannot exceed the remaining balance.")
        else:
            payment = Payment(
                user_id=current_user.id,
                invoice_id=invoice.id,
                payment_date=payment_form.payment_date.data,
                payment_method=(payment_form.payment_method.data or "").strip() or None,
                reference_number=(payment_form.reference_number.data or "").strip() or None,
                amount=amount,
            )
            db.session.add(payment)
            db.session.flush()
            invoice.refresh_payment_state()
            db.session.commit()
            flash("Payment recorded.", "success")
            return redirect(url_for("invoices.detail", invoice_id=invoice.id))

    email_form = SendEmailForm()
    return render_template("invoices/detail.html", invoice=invoice,
                           payment_form=payment_form, email_form=email_form), 400


# ─── PDF Download ────────────────────────────────────────────────────────────

@invoices_bp.get("/<int:invoice_id>/pdf")
@login_required
def download_pdf(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    invoice.refresh_payment_state()
    db.session.commit()
    content, mimetype = generate_pdf(invoice)
    ext = ".pdf" if mimetype == "application/pdf" else ".html"
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}{ext}"'},
    )


# ─── DOCX Download ───────────────────────────────────────────────────────────

@invoices_bp.get("/<int:invoice_id>/docx")
@login_required
def download_docx(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    invoice.refresh_payment_state()
    db.session.commit()
    content = generate_docx(invoice)
    return Response(
        content,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.docx"'},
    )


# ─── HTML Print View ─────────────────────────────────────────────────────────

@invoices_bp.get("/<int:invoice_id>/print")
@login_required
def print_view(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    invoice.refresh_payment_state()
    db.session.commit()
    tmpl = invoice.template if invoice.template in {"classic", "modern", "minimal"} else "classic"
    return render_template(f"invoices/{tmpl}.html", invoice=invoice, print_mode=True)


# ─── Legacy HTML download ─────────────────────────────────────────────────────

@invoices_bp.get("/<int:invoice_id>/download")
@login_required
def download(invoice_id):
    """Backward-compatible HTML invoice download."""
    invoice = _get_owned_invoice(invoice_id)
    invoice.refresh_payment_state()
    db.session.commit()
    tmpl = invoice.template if invoice.template in {"classic", "modern", "minimal"} else "classic"
    html = render_template(f"invoices/{tmpl}.html", invoice=invoice)
    return Response(
        html,
        mimetype="text/html",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.html"'},
    )


# ─── Send Email ──────────────────────────────────────────────────────────────

@invoices_bp.post("/<int:invoice_id>/email")
@login_required
def send_email(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    email_form = SendEmailForm()
    if email_form.validate_on_submit():
        ok, err = send_invoice_email(
            invoice,
            email_form.recipient_email.data.strip(),
            email_form.subject.data.strip(),
            email_form.body.data.strip(),
        )
        if ok:
            from datetime import datetime
            invoice.email_sent_at = datetime.utcnow()
            db.session.commit()
            flash("Invoice emailed successfully.", "success")
        else:
            flash(f"Email failed: {err}", "danger")
    else:
        flash("Please check the email form fields.", "danger")
    return redirect(url_for("invoices.detail", invoice_id=invoice.id))


# ─── WhatsApp Share ──────────────────────────────────────────────────────────

@invoices_bp.get("/<int:invoice_id>/whatsapp")
@login_required
def whatsapp_share(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    text = (
        f"Hello {invoice.customer.name},%0A%0A"
        f"Invoice *{invoice.invoice_number}* for *{invoice.currency} {invoice.total_amount}* "
        f"is ready.%0ADue date: *{invoice.due_date.strftime('%d %b %Y')}*%0A%0A"
        f"Regards,%0A{invoice.user.name}"
    )
    wa_url = f"https://wa.me/?text={text}"
    return redirect(wa_url)


# ─── Duplicate ───────────────────────────────────────────────────────────────

@invoices_bp.post("/<int:invoice_id>/duplicate")
@login_required
def duplicate(invoice_id):
    invoice = _get_owned_invoice(invoice_id)
    dup = Invoice(
        user_id=current_user.id,
        customer_id=invoice.customer_id,
        invoice_number=_next_invoice_number(),
        invoice_date=date.today(),
        due_date=max(date.today(), invoice.due_date),
        status="Draft",
        transaction_type=invoice.transaction_type,
        template=invoice.template,
        currency=invoice.currency,
        payment_terms=invoice.payment_terms,
        notes=invoice.notes,
        subtotal=invoice.subtotal,
        discount_total=invoice.discount_total,
        taxable_amount=invoice.taxable_amount,
        cgst_amount=invoice.cgst_amount,
        sgst_amount=invoice.sgst_amount,
        igst_amount=invoice.igst_amount,
        total_amount=invoice.total_amount,
        amount_paid=Decimal("0.00"),
    )
    for item in invoice.items:
        dup.items.append(InvoiceItem(
            product_id=item.product_id,
            item_name=item.item_name,
            description=item.description,
            hsn_sac=item.hsn_sac,
            quantity=item.quantity,
            unit_price=item.unit_price,
            discount=item.discount,
            gst_rate=item.gst_rate,
            tax_amount=item.tax_amount,
            line_total=item.line_total,
        ))
    db.session.add(dup)
    db.session.commit()
    flash(f"Invoice duplicated as {dup.invoice_number}.", "success")
    return redirect(url_for("invoices.detail", invoice_id=dup.id))


# ─── Razorpay Standard Checkout Integration ───────────────────────────────────

@invoices_bp.post("/public/<token>/create-razorpay-order")
@csrf.exempt
def create_razorpay_order(token):
    import razorpay
    invoice = Invoice.query.filter_by(share_token=token).first_or_404()
    if invoice.status == "Paid":
        return jsonify({"error": "Invoice is already paid"}), 400

    amount_due = invoice.balance_due if invoice.balance_due > 0 else invoice.total_amount
    amount_paise = int(round(Decimal(amount_due) * 100))

    if amount_paise < 100:
        return jsonify({"error": "Minimum payment amount is ₹1.00 (100 paise)"}), 400

    key_id = (current_app.config.get("RAZORPAY_KEY_ID") or os.getenv("RAZORPAY_KEY_ID") or "rzp_test_TPB0DS6qkyq6PJ").strip().strip('"').strip("'")
    key_secret = (current_app.config.get("RAZORPAY_KEY_SECRET") or os.getenv("RAZORPAY_KEY_SECRET") or "XEZxF9ebnFg6ofGSc8evy3Eg").strip().strip('"').strip("'")

    client = razorpay.Client(auth=(key_id, key_secret))

    order_id = None
    try:
        order_data = {
            "amount": amount_paise,
            "currency": invoice.currency or "INR",
            "receipt": f"inv_{invoice.id}",
            "notes": {
                "invoice_number": invoice.invoice_number,
                "customer_name": invoice.customer.name if invoice.customer else "Client"
            }
        }
        order = client.order.create(data=order_data)
        order_id = order["id"]
    except Exception:
        order_id = f"order_test_{token[:12]}"

    return jsonify({
        "order_id": order_id,
        "amount": amount_paise,
        "currency": invoice.currency or "INR",
        "key_id": key_id,
        "invoice_number": invoice.invoice_number,
        "company_name": invoice.user.company_settings.company_name if invoice.user and invoice.user.company_settings else "InvoicePro",
        "customer_name": invoice.customer.name if invoice.customer else "Client",
        "customer_email": invoice.customer.email if invoice.customer else "",
        "customer_phone": invoice.customer.phone if invoice.customer else "",
    })


@invoices_bp.post("/public/<token>/verify-razorpay-payment")
@csrf.exempt
def verify_razorpay_payment(token):
    import razorpay
    invoice = Invoice.query.filter_by(share_token=token).first_or_404()

    data = request.get_json(silent=True) or request.form
    payment_id = data.get("razorpay_payment_id")
    order_id = data.get("razorpay_order_id")
    signature = data.get("razorpay_signature")

    if not payment_id or not order_id or not signature:
        return jsonify({"success": False, "error": "Missing required signature verification fields"}), 400

    key_id = (current_app.config.get("RAZORPAY_KEY_ID") or os.getenv("RAZORPAY_KEY_ID") or "rzp_test_TPB0DS6qkyq6PJ").strip().strip('"').strip("'")
    key_secret = (current_app.config.get("RAZORPAY_KEY_SECRET") or os.getenv("RAZORPAY_KEY_SECRET") or "XEZxF9ebnFg6ofGSc8evy3Eg").strip().strip('"').strip("'")

    client = razorpay.Client(auth=(key_id, key_secret))
    params_dict = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature
    }

    try:
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"success": False, "error": "Razorpay payment signature verification failed!"}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    if invoice.status != "Paid":
        amount_paid = invoice.balance_due if invoice.balance_due > 0 else invoice.total_amount
        payment = Payment(
            invoice_id=invoice.id,
            user_id=invoice.user_id,
            payment_date=date.today(),
            amount=amount_paid,
            payment_method="Razorpay",
            reference_number=payment_id,
        )
        db.session.add(payment)
        invoice.amount_paid = Decimal(invoice.amount_paid or 0) + Decimal(amount_paid)
        invoice.status = "Paid"
        db.session.commit()

    flash("🎉 Razorpay Payment Verified & Received! Thank you for your payment.", "success")
    return jsonify({"success": True, "message": "Payment verified and invoice marked as Paid!"})
