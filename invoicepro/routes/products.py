from flask import Blueprint, abort, flash, redirect, render_template, url_for, request
from flask_login import current_user, login_required
from sqlalchemy import or_

from invoicepro.database.database import db
from invoicepro.database.models import Product
from invoicepro.forms import ProductForm


products_bp = Blueprint("products", __name__, url_prefix="/products")


def _get_owned_product(product_id):
    product = db.session.get(Product, product_id)
    if not product or product.user_id != current_user.id:
        abort(404)
    return product


@products_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    search = (request.args.get("q") or "").strip()
    form = ProductForm(unit="Nos", price=0, gst_rate="18")
    if form.validate_on_submit():
        name = form.name.data.strip()
        existing = Product.query.filter_by(user_id=current_user.id, name=name).first()
        if existing:
            flash(f"A product named '{name}' already exists.", "danger")
        else:
            product = Product(
                user_id=current_user.id,
                name=name,
                description=(form.description.data or "").strip() or None,
                hsn_sac=(form.hsn_sac.data or "").strip() or None,
                price=form.price.data,
                gst_rate=form.gst_rate.data,
                unit=form.unit.data.strip(),
            )
            db.session.add(product)
            try:
                db.session.commit()
                flash("Product created.", "success")
                return redirect(url_for("products.index"))
            except Exception:
                db.session.rollback()
                flash(f"A product named '{name}' already exists.", "danger")

    q = Product.query.filter_by(user_id=current_user.id)
    if search:
        q = q.filter(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
            )
        )
    products = q.order_by(Product.created_at.desc()).all()
    return render_template("products/index.html", form=form, products=products, search=search)


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id):
    product = _get_owned_product(product_id)
    form = ProductForm(obj=product)
    # SelectField needs string value
    if request.method == "GET":
        form.gst_rate.data = str(int(product.gst_rate))
    if form.validate_on_submit():
        name = form.name.data.strip()
        existing = Product.query.filter(
            Product.user_id == current_user.id,
            Product.name == name,
            Product.id != product_id,
        ).first()
        if existing:
            flash(f"A product named '{name}' already exists.", "danger")
        else:
            product.name = name
            product.description = (form.description.data or "").strip() or None
            product.hsn_sac = (form.hsn_sac.data or "").strip() or None
            product.price = form.price.data
            product.gst_rate = form.gst_rate.data
            product.unit = form.unit.data.strip()
            try:
                db.session.commit()
                flash("Product updated.", "success")
                return redirect(url_for("products.index"))
            except Exception:
                db.session.rollback()
                flash(f"A product named '{name}' already exists.", "danger")

    return render_template("products/edit.html", form=form, product=product)


@products_bp.post("/<int:product_id>/archive")
@login_required
def archive(product_id):
    product = _get_owned_product(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    flash(
        "Product activated." if product.is_active else "Product archived.",
        "success",
    )
    return redirect(url_for("products.index"))
