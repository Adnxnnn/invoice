from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect


login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"

migrate = Migrate()
csrf = CSRFProtect()
