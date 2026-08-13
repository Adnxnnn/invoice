from decimal import Decimal

from sqlalchemy import func

from invoicepro.database.database import db
from invoicepro.database.models import Customer, Invoice, Payment, Product
from invoicepro.services.report_generator import (
    monthly_revenue_chart,
    top_customers,
    best_selling_products,
)


def get_dashboard_summary(user_id):
    invoices = Invoice.query.filter_by(user_id=user_id)

    total_revenue = invoices.with_entities(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar()
    total_paid = invoices.with_entities(func.coalesce(func.sum(Invoice.amount_paid), 0)).scalar()
    overdue_amount = (
        invoices.filter(Invoice.status == "Overdue")
        .with_entities(func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), 0))
        .scalar()
    )
    pending_amount = (
        invoices.filter(Invoice.status.in_(("Pending", "Sent", "Draft")))
        .with_entities(func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), 0))
        .scalar()
    )

    chart_data = monthly_revenue_chart(user_id)
    customers_top = top_customers(user_id)
    products_top = best_selling_products(user_id)

    # Status distribution for doughnut chart
    statuses = ["Draft", "Sent", "Pending", "Paid", "Overdue", "Cancelled"]
    status_counts = {}
    for s in statuses:
        status_counts[s] = invoices.filter(Invoice.status == s).count()

    return {
        "total_revenue": Decimal(total_revenue or 0),
        "paid_amount": Decimal(total_paid or 0),
        "pending_amount": Decimal(pending_amount or 0),
        "overdue_amount": Decimal(overdue_amount or 0),
        "total_invoices": invoices.count(),
        "total_customers": Customer.query.filter_by(user_id=user_id).count(),
        "total_products": Product.query.filter_by(user_id=user_id).count(),
        "recent_invoices": invoices.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).limit(10).all(),
        "recent_payments": (
            Payment.query.filter_by(user_id=user_id)
            .order_by(Payment.payment_date.desc(), Payment.id.desc())
            .limit(5)
            .all()
        ),
        "chart_monthly": chart_data,
        "top_customers": customers_top,
        "top_products": products_top,
        "status_counts": status_counts,
    }
