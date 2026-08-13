from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def unique_upload_path(directory, filename):
    safe_name = secure_filename(filename)
    extension = Path(safe_name).suffix.lower()
    return Path(directory) / f"{uuid4().hex}{extension}"
