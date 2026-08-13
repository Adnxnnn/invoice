import io
from datetime import date

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from invoicepro.services.report_generator import (
    revenue_summary,
    gst_summary,
    customer_report,
    product_report,
    export_invoices_csv,
    export_invoices_excel,
)


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

REPORT_TYPES = [
    ("revenue", "Revenue Summary"),
    ("gst", "GST Summary"),
    ("customers", "Customer Report"),
    ("products", "Product Sales"),
]

PERIOD_CHOICES = [
    ("today", "Today"),
    ("week", "This Week"),
    ("month", "This Month"),
    ("year", "This Year"),
    ("custom", "Custom Range"),
]


@reports_bp.get("/")
@login_required
def index():
    report_type = (request.args.get("report") or "revenue").strip()
    period = (request.args.get("period") or "month").strip()
    date_from_str = (request.args.get("date_from") or "").strip()
    date_to_str = (request.args.get("date_to") or "").strip()

    date_from = None
    date_to = None
    if period == "custom":
        try:
            date_from = date.fromisoformat(date_from_str) if date_from_str else date.today().replace(day=1)
            date_to = date.fromisoformat(date_to_str) if date_to_str else date.today()
        except ValueError:
            date_from = date.today().replace(day=1)
            date_to = date.today()

    data = {}
    if report_type == "revenue":
        data = revenue_summary(current_user.id, period, date_from, date_to)
    elif report_type == "gst":
        data = gst_summary(current_user.id, period, date_from, date_to)
    elif report_type == "customers":
        data = {"rows": customer_report(current_user.id)}
    elif report_type == "products":
        data = {"rows": product_report(current_user.id)}

    return render_template(
        "reports/index.html",
        report_type=report_type,
        period=period,
        date_from_str=date_from_str,
        date_to_str=date_to_str,
        data=data,
        report_types=REPORT_TYPES,
        period_choices=PERIOD_CHOICES,
    )


@reports_bp.get("/export")
@login_required
def export():
    fmt = (request.args.get("format") or "csv").strip().lower()
    period = (request.args.get("period") or "month").strip()
    date_from_str = (request.args.get("date_from") or "").strip()
    date_to_str = (request.args.get("date_to") or "").strip()

    date_from = None
    date_to = None
    if period == "custom":
        try:
            date_from = date.fromisoformat(date_from_str)
            date_to = date.fromisoformat(date_to_str)
        except ValueError:
            pass

    if fmt == "excel":
        content = export_invoices_excel(current_user.id, period, date_from, date_to)
        return Response(
            content,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=invoices.xlsx"},
        )
    else:
        content = export_invoices_csv(current_user.id, period, date_from, date_to)
        return Response(
            content,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=invoices.csv"},
        )
