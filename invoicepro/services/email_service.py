"""
Email Service
=============
Sends invoice emails via SMTP using credentials from environment variables.
Never hard-codes credentials.

Usage:
    from invoicepro.services.email_service import send_invoice_email
    ok, err = send_invoice_email(invoice, recipient, subject, body)
"""

import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from invoicepro.services.pdf_generator import generate_pdf, pdf_filename


def _is_configured() -> bool:
    return bool(
        current_app.config.get("MAIL_SERVER")
        and current_app.config.get("MAIL_USERNAME")
        and current_app.config.get("MAIL_PASSWORD")
    )


def send_invoice_email(
    invoice,
    recipient_email: str,
    subject: str,
    body: str,
) -> tuple[bool, str]:
    """
    Send an email with the invoice PDF attached.

    Returns (success: bool, error_message: str).
    """
    if not _is_configured():
        return False, (
            "Email is not configured. Set MAIL_SERVER, MAIL_USERNAME, and "
            "MAIL_PASSWORD in your .env file."
        )

    try:
        pdf_bytes, mime_type = generate_pdf(invoice)
        filename = pdf_filename(invoice)

        msg = MIMEMultipart()
        msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"] or current_app.config["MAIL_USERNAME"]
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(pdf_bytes)
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        msg.attach(attachment)

        server = current_app.config["MAIL_SERVER"]
        port = current_app.config["MAIL_PORT"]
        use_tls = current_app.config["MAIL_USE_TLS"]
        username = current_app.config["MAIL_USERNAME"]
        password = current_app.config["MAIL_PASSWORD"]

        with smtplib.SMTP(server, port) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(username, password)
            smtp.sendmail(msg["From"], [recipient_email], msg.as_string())

        return True, ""
    except Exception as exc:
        return False, str(exc)
