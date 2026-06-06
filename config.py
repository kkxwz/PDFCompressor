"""
PDF Compressor - Global Configuration

Supports both development and PyInstaller frozen environments.
"""
import os
import sys
import platform

# ========== Path Detection ==========

def is_frozen() -> bool:
    """Check if running in PyInstaller frozen environment"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_app_dir() -> str:
    """Get application data directory (for uploads/outputs, must be writable)"""
    if is_frozen():
        system = platform.system()
        if system == "Windows":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            app_dir = os.path.join(base, "PDFCompressor")
        elif system == "Darwin":
            app_dir = os.path.join(os.path.expanduser("~"), "Library",
                                   "Application Support", "PDFCompressor")
        else:
            app_dir = os.path.join(os.path.expanduser("~"), ".pdf-compressor")
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return app_dir


def get_resource_dir() -> str:
    """Get resource directory (templates/static/Ghostscript, read-only)"""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# ========== Base Paths ==========

APP_DIR = get_app_dir()
RESOURCE_DIR = get_resource_dir()

# Server config
HOST = "127.0.0.1"
PORT = 5000
DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

# Upload config
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {"pdf"}
UPLOAD_FOLDER = os.path.join(APP_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(APP_DIR, "outputs")

# Auto cleanup interval (seconds)
FILE_CLEANUP_SECONDS = 10 * 60  # 10 minutes

# Compression timeout (seconds)
COMPRESS_TIMEOUT = 5 * 60  # 5 minutes

# ========== Ghostscript Paths ==========

def _build_gs_paths() -> list:
    """Build Ghostscript executable search paths"""
    paths = []

    if is_frozen():
        # Frozen mode: prefer bundled Ghostscript
        vendor_dir = os.path.join(RESOURCE_DIR, "vendor", "ghostscript")
        system = platform.system()

        if system == "Darwin":
            # macOS: Universal Binary
            paths.append(os.path.join(vendor_dir, "gs"))
        elif system == "Windows":
            # Windows: select by architecture
            machine = platform.machine().lower()
            if machine in ("arm64", "aarch64"):
                paths.append(os.path.join(vendor_dir, "arm64", "gswin64c.exe"))
            paths.append(os.path.join(vendor_dir, "x64", "gswin64c.exe"))
            paths.append(os.path.join(vendor_dir, "gswin64c.exe"))

    # Development mode or fallback: vendor dir + system PATH
    paths.extend([
        os.path.join(RESOURCE_DIR, "vendor", "ghostscript", "mac", "gs"),
        os.path.join(RESOURCE_DIR, "vendor", "ghostscript", "windows", "gswin64c.exe"),
        "gs",           # macOS/Linux system PATH
        "gswin64c",     # Windows system PATH
        "gswin32c",     # Windows 32-bit
    ])

    return paths


GS_PATHS = _build_gs_paths()

# ========== Ensure Directories Exist ==========

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
