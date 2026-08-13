"""
PDF Generator Service
=====================
Renders invoice HTML templates and converts to PDF via WeasyPrint.
Falls back to HTML download if WeasyPrint is not available (e.g. missing system
GTK/Pango libraries on Windows).
"""

from pathlib import Path

from flask import current_app, render_template

# Try importing WeasyPrint – it requires system GTK libraries on Windows.
try:
    from weasyprint import HTML as WeasyHTML

    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False


def _template_name(template: str) -> str:
    allowed = {"classic", "modern", "minimal"}
    return template if template in allowed else "classic"


def render_invoice_html(invoice) -> str:
    """Render invoice as HTML string using the invoice's chosen template."""
    tmpl = _template_name(invoice.template)
    return render_template(f"invoices/{tmpl}.html", invoice=invoice)


def generate_pdf(invoice) -> tuple[bytes, str]:
    """
    Generate a PDF for the given invoice.

    Returns (content_bytes, mimetype).
    Falls back to HTML bytes with text/html mimetype if WeasyPrint unavailable.
    """
    html_str = render_invoice_html(invoice)

    if WEASYPRINT_AVAILABLE:
        # Build base URL so relative static assets resolve correctly
        static_url = str(
            Path(current_app.root_path) / "static"
        )
        pdf_bytes = WeasyHTML(
            string=html_str,
            base_url=f"file:///{static_url}/",
        ).write_pdf()
        return pdf_bytes, "application/pdf"

    # Graceful fallback – deliver as HTML
    return html_str.encode("utf-8"), "text/html"


def pdf_filename(invoice) -> str:
    """Return the suggested download filename."""
    if WEASYPRINT_AVAILABLE:
        return f"{invoice.invoice_number}.pdf"
    return f"{invoice.invoice_number}.html"
