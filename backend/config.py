"""
Centralized path configuration for the backend.
All modules should import paths from here instead of computing them via __file__ traversal.
"""
import os
from pathlib import Path

# Absolute path to the backend directory (where this config.py lives)
BACKEND_DIR = Path(__file__).resolve().parent

# Standard directories
UPLOADS_DIR = BACKEND_DIR / "uploads"
TEMP_UPLOADS_DIR = UPLOADS_DIR / "temp"
CV_DIR = UPLOADS_DIR / "cv"
EXPORTS_DIR = BACKEND_DIR / "exports"
PAYROLL_EXPORTS_DIR = EXPORTS_DIR / "payroll"
DOCUMENTS_DIR = BACKEND_DIR / "documents"
TEMPLATES_DIR = BACKEND_DIR / "templates"
EMAIL_TEMPLATES_DIR = TEMPLATES_DIR / "email"

# Server base URL (used to build download URLs and resolve them back to abs paths)
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

# URL prefix → directory mapping (for url_to_abs_path resolution)
_URL_DIR_MAP = {
    "/api/uploads/cv/": CV_DIR,
    "/api/uploads/temp/": TEMP_UPLOADS_DIR,
    "/api/uploads/payroll/": PAYROLL_EXPORTS_DIR,
    "/api/exports/": EXPORTS_DIR,
    "/uploads/cv/": CV_DIR,
    "/uploads/temp/": TEMP_UPLOADS_DIR,
    "/uploads/payroll/": PAYROLL_EXPORTS_DIR,
    "/uploads/exports/": EXPORTS_DIR,
}


def url_to_abs_path(server_url: str) -> Path | None:
    """
    Convert a server URL to an absolute filesystem path.
    
    Example:
        "http://localhost:5000/uploads/cv/CV_Rafael.pdf"
        → Path("D:/PINET/.../backend/uploads/cv/CV_Rafael.pdf")
    
    Returns None if URL doesn't match any known prefix.
    """
    # Strip base URL prefix if present
    url = server_url
    for prefix in (BASE_URL, "http://localhost:5000", "http://127.0.0.1:5000"):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break

    for url_prefix, directory in _URL_DIR_MAP.items():
        if url.startswith(url_prefix):
            filename = url[len(url_prefix):]
            return directory / filename

    return None


# Ensure directories exist
for d in [CV_DIR, TEMP_UPLOADS_DIR, PAYROLL_EXPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
