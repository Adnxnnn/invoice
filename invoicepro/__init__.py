from pathlib import Path

import click
from flask import Flask, redirect, send_from_directory, url_for

from config import DevelopmentConfig
from invoicepro.database.database import db
from invoicepro.extensions import csrf, login_manager, migrate


def create_app(config_object=DevelopmentConfig):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

    _ensure_directories(app)
    _register_extensions(app)
    _register_blueprints(app)
    _register_commands(app)
    _register_shell_context(app)
    _register_routes(app)

    return app


def _ensure_directories(app):
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    for key in ("UPLOAD_FOLDER", "LOGO_UPLOAD_FOLDER", "SIGNATURE_UPLOAD_FOLDER",
                "GENERATED_INVOICES_FOLDER"):
        Path(app.config[key]).mkdir(parents=True, exist_ok=True)


def _register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    _auto_migrate(app)


def _auto_migrate(app):
    with app.app_context():
        import invoicepro.database.models  # noqa: F401
        from sqlalchemy import inspect, text
        try:
            db.create_all()
            inspector = inspect(db.engine)
            db_tables = inspector.get_table_names()
            
            for mapper in db.Model.registry.mappers:
                cls = mapper.class_
                if hasattr(cls, '__tablename__'):
                    table_name = cls.__tablename__
                    if table_name in db_tables:
                        existing_cols = {c['name'] for c in inspector.get_columns(table_name)}
                        for column in cls.__table__.columns:
                            if column.name not in existing_cols:
                                col_type = column.type.compile(db.engine.dialect)
                                default_str = ""
                                if column.default is not None and column.default.arg is not None:
                                    arg = column.default.arg
                                    if isinstance(arg, (int, float)):
                                        default_str = f" DEFAULT {arg}"
                                    elif isinstance(arg, str):
                                        default_str = f" DEFAULT '{arg}'"
                                sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default_str}"
                                db.session.execute(text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _register_blueprints(app):
    from invoicepro.routes.auth import auth_bp
    from invoicepro.routes.customers import customers_bp
    from invoicepro.routes.dashboard import dashboard_bp
    from invoicepro.routes.invoices import invoices_bp
    from invoicepro.routes.products import products_bp
    from invoicepro.routes.reports import reports_bp
    from invoicepro.routes.settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)


def _register_shell_context(app):
    from invoicepro.database.models import (
        CompanySettings, Customer, Invoice, InvoiceItem, Payment, Product, User,
    )

    @app.shell_context_processor
    def shell_context():
        return {
            "db": db,
            "User": User,
            "CompanySettings": CompanySettings,
            "Customer": Customer,
            "Product": Product,
            "Invoice": Invoice,
            "InvoiceItem": InvoiceItem,
            "Payment": Payment,
        }


def _register_commands(app):
    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
        click.echo("Database initialized.")


def _register_routes(app):
    @app.get("/")
    def index():
        return redirect(url_for("dashboard.home"))

    @app.get("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(Path(app.root_path) / "uploads", filename)
