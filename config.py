import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# Check if running in Vercel serverless environment
IS_VERCEL = os.getenv("VERCEL") == "1"

# Database URI resolution (PostgreSQL or SQLite fallback)
raw_db_url = os.getenv("DATABASE_URL")
if raw_db_url:
    if raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
    db_uri = raw_db_url
else:
    if IS_VERCEL:
        db_uri = "sqlite:////tmp/invoicepro.db"
    else:
        db_uri = f"sqlite:///{BASE_DIR / 'instance' / 'invoicepro.db'}"

# Base writable directory for serverless environments
writable_dir = Path("/tmp") if IS_VERCEL else BASE_DIR


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = db_uri
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year cache for static CSS/JS
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    UPLOAD_FOLDER = str(writable_dir / "uploads")
    LOGO_UPLOAD_FOLDER = str(writable_dir / "uploads" / "logos")
    SIGNATURE_UPLOAD_FOLDER = str(writable_dir / "uploads" / "signatures")
    GENERATED_INVOICES_FOLDER = str(writable_dir / "generated_invoices")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    WTF_CSRF_TIME_LIMIT = None

    # Razorpay Gateway Configuration
    RAZORPAY_KEY_ID = (os.getenv("RAZORPAY_KEY_ID") or "rzp_test_TPB0DS6qkyq6PJ").strip().strip('"').strip("'")
    RAZORPAY_KEY_SECRET = (os.getenv("RAZORPAY_KEY_SECRET") or "XEZxF9ebnFg6ofGSc8evy3Eg").strip().strip('"').strip("'")

    # Email / SMTP
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
