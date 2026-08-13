from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from invoicepro.database.database import db
from invoicepro.database.models import Customer
from invoicepro.forms import CustomerForm


customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


def _get_owned_customer(customer_id):
    customer = db.session.get(Customer, customer_id)
    if not customer or customer.user_id != current_user.id:
        abort(404)
    return customer


@customers_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    search = (request.args.get("q") or "").strip()
    form = CustomerForm()
    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower() or None
        existing = Customer.query.filter_by(user_id=current_user.id, email=email).first() if email else None
        if existing:
            flash(f"A customer with email '{email}' already exists.", "danger")
        else:
            customer = Customer(
                user_id=current_user.id,
                name=form.name.data.strip(),
                email=email,
                phone=(form.phone.data or "").strip() or None,
                address=(form.address.data or "").strip() or None,
                shipping_address=(form.shipping_address.data or "").strip() or None,
                gstin=(form.gstin.data or "").strip().upper() or None,
                notes=(form.notes.data or "").strip() or None,
            )
            db.session.add(customer)
            try:
                db.session.commit()
                flash("Customer created.", "success")
                return redirect(url_for("customers.index"))
            except Exception:
                db.session.rollback()
                flash("Could not create customer (duplicate email or invalid data).", "danger")

    q = Customer.query.filter_by(user_id=current_user.id)
    if search:
        q = q.filter(
            or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
            )
        )
    customers = q.order_by(Customer.name.asc()).all()
    return render_template("customers/index.html", form=form, customers=customers, search=search)


@customers_bp.get("/<int:customer_id>")
@login_required
def detail(customer_id):
    customer = _get_owned_customer(customer_id)
    return render_template("customers/detail.html", customer=customer)


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit(customer_id):
    customer = _get_owned_customer(customer_id)
    form = CustomerForm(obj=customer)
    if form.validate_on_submit():
        customer.name = form.name.data.strip()
        customer.email = (form.email.data or "").strip().lower() or None
        customer.phone = (form.phone.data or "").strip() or None
        customer.address = (form.address.data or "").strip() or None
        customer.shipping_address = (form.shipping_address.data or "").strip() or None
        customer.gstin = (form.gstin.data or "").strip().upper() or None
        customer.notes = (form.notes.data or "").strip() or None
        db.session.commit()
        flash("Customer updated.", "success")
        return redirect(url_for("customers.detail", customer_id=customer.id))

    return render_template("customers/edit.html", form=form, customer=customer)


@customers_bp.post("/<int:customer_id>/delete")
@login_required
def delete(customer_id):
    customer = _get_owned_customer(customer_id)
    if customer.invoices:
        flash("This customer has invoices and cannot be deleted.", "warning")
    else:
        db.session.delete(customer)
        db.session.commit()
        flash("Customer deleted.", "success")
    return redirect(url_for("customers.index"))
