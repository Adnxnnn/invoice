from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from invoicepro.services.dashboard_service import get_dashboard_summary


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.get("/")
@login_required
def home():
    summary = get_dashboard_summary(current_user.id)
    return render_template("dashboard/home.html", summary=summary)
