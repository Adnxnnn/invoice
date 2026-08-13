import sys
from pathlib import Path

# Ensure root directory is on sys.path for Vercel serverless execution
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from invoicepro import create_app

app = create_app()
