from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from invoicepro.database.database import db
from invoicepro.database.models import CompanySettings, User
from invoicepro.forms import ForgotPasswordForm, LoginForm, RegisterForm


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = db.session.execute(
            select(User).where(User.email == form.email.data.lower().strip())
        ).scalar_one_or_none()
        if existing_user:
            form.email.errors.append("An account with this email already exists.")
        else:
            user = User(
                name=form.name.data.strip(),
                email=form.email.data.lower().strip(),
                phone=(form.phone.data or "").strip() or None,
            )
            user.set_password(form.password.data)

            settings = CompanySettings(
                company_name=(form.company_name.data or "").strip() or None,
                address=(form.address.data or "").strip() or None,
                website=(form.website.data or "").strip() or None,
                invoice_prefix=form.invoice_prefix.data.strip().upper(),
            )
            user.company_settings = settings

            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your account is ready.", "success")
            return redirect(url_for("dashboard.home"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            select(User).where(User.email == form.email.data.lower().strip())
        ).scalar_one_or_none()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_url = request.args.get("next")
            flash("Welcome back.", "success")
            return redirect(next_url or url_for("dashboard.home"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        flash(
            "Password reset flow is not wired yet. The UI and route are ready for Phase 2.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)
