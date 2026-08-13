from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from invoicepro.database.database import db
from invoicepro.forms import CompanySettingsForm
from invoicepro.services.file_service import allowed_file, unique_upload_path


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def _save_optional_upload(field_name, destination_key, current_value=None):
    file = request.files.get(field_name)
    if not file or not file.filename:
        return current_value
    if not allowed_file(file.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
        raise ValueError("Upload a PNG, JPG, JPEG, or WEBP image.")
    upload_path = unique_upload_path(current_app.config[destination_key], file.filename)
    file.save(upload_path)
    return str(Path(upload_path).relative_to(current_app.root_path))


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    settings = current_user.company_settings
    form = CompanySettingsForm(obj=settings)

    if request.method == "GET":
        # SelectField needs string values
        if settings.default_tax_rate is not None:
            form.default_tax_rate.data = str(int(settings.default_tax_rate))

    if form.validate_on_submit():
        try:
            settings.company_name = (form.company_name.data or "").strip() or None
            settings.address = (form.address.data or "").strip() or None
            settings.phone = (form.phone.data or "").strip() or None
            settings.email = (form.email.data or "").strip() or None
            settings.gstin = (form.gstin.data or "").strip().upper() or None
            settings.website = (form.website.data or "").strip() or None
            settings.invoice_prefix = form.invoice_prefix.data.strip().upper()
            settings.default_currency = form.default_currency.data
            settings.default_tax_rate = form.default_tax_rate.data
            settings.payment_instructions = (form.payment_instructions.data or "").strip() or None
            settings.footer_text = (form.footer_text.data or "").strip() or None
            settings.tax_information = (form.tax_information.data or "").strip() or None
            settings.company_logo = _save_optional_upload(
                "logo", "LOGO_UPLOAD_FOLDER", current_value=settings.company_logo,
            )
            settings.signature = _save_optional_upload(
                "signature", "SIGNATURE_UPLOAD_FOLDER", current_value=settings.signature,
            )
        except ValueError as exc:
            form.logo.errors.append(str(exc))
        else:
            db.session.commit()
            flash("Company settings updated.", "success")
            return redirect(url_for("settings.index"))

    return render_template("settings/index.html", form=form, settings=settings)
