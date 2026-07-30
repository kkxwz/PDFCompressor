"""
SlimPDF - Flask Main Application

Start:
    python app.py

Visit: http://127.0.0.1:5000
"""
import os
import sys
import logging
import webbrowser
import threading
import atexit
from logging.handlers import RotatingFileHandler

from flask import Flask, Response, render_template, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

import config
from routes.upload import upload_bp
from routes.compress import compress_bp
from routes.health import health_bp


def _setup_logging() -> None:
    """Console logging always; in frozen (desktop) mode also persist logs to
    APP_DIR/logs so user-side issues can be diagnosed after the fact"""
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if config.is_frozen():
        log_dir = os.path.join(config.APP_DIR, "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            handlers.append(RotatingFileHandler(
                os.path.join(log_dir, "slimpdf.log"),
                maxBytes=1 * 1024 * 1024,  # 1MB x 3 backups
                backupCount=3,
                encoding="utf-8",
            ))
        except OSError:
            pass  # Logging must never block startup

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


_setup_logging()
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create Flask application"""
    # Ensure required directories exist
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)

    resource_dir = config.RESOURCE_DIR
    template_folder = os.path.join(resource_dir, "templates")
    static_folder = os.path.join(resource_dir, "static")

    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=static_folder
    )

    # Configure max upload size
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    # Register blueprints
    app.register_blueprint(upload_bp)
    app.register_blueprint(compress_bp)
    app.register_blueprint(health_bp)

    # Return JSON (not Flask's default HTML page) when MAX_CONTENT_LENGTH is hit
    @app.errorhandler(413)
    def request_entity_too_large(e: RequestEntityTooLarge) -> tuple[Response, int]:
        return jsonify({
            "error": "FILE_TOO_LARGE",
            "message": f"File too large, max supported {config.MAX_UPLOAD_MB}MB"
        }), 413

    # Home route (injects config-derived values so the frontend never
    # hardcodes the upload limit / cleanup interval / version)
    @app.route("/")
    def index() -> str:
        return render_template(
            "index.html",
            max_upload_mb=config.MAX_UPLOAD_MB,
            cleanup_minutes=config.FILE_CLEANUP_SECONDS // 60,
            version=config.VERSION,
        )

    return app


app = create_app()


def open_browser() -> None:
    """Auto-open browser"""
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")


def cleanup_temp_files() -> None:
    """Clean up temp files on exit"""
    import shutil
    for folder in [config.UPLOAD_FOLDER, config.OUTPUT_FOLDER]:
        if os.path.isdir(folder):
            try:
                for f in os.listdir(folder):
                    filepath = os.path.join(folder, f)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
            except Exception:
                pass


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info(f"SlimPDF v{config.VERSION} starting...")
    logger.info(f"Visit: http://{config.HOST}:{config.PORT}")
    logger.info(f"App data: {config.APP_DIR}")
    logger.info(f"Resource dir: {config.RESOURCE_DIR}")
    logger.info(f"Frozen mode: {'Yes' if config.is_frozen() else 'No'}")
    logger.info("=" * 50)

    # Check Ghostscript
    from compress.engine import find_ghostscript, get_gs_version
    gs_path = find_ghostscript()
    if gs_path:
        gs_version = get_gs_version(gs_path)
        logger.info(f"Ghostscript: {gs_path} (v{gs_version})")
    else:
        logger.warning("Ghostscript not found! Compression unavailable.")

    # Clean up files left over from a previous abnormal exit (atexit may not
    # have run if the process was killed), then register exit cleanup
    cleanup_temp_files()
    atexit.register(cleanup_temp_files)

    # Delayed browser open (auto-open in both frozen and production mode)
    if not config.DEBUG:
        threading.Timer(1.5, open_browser).start()
        print(f"\n{'=' * 50}")
        print(f"  SlimPDF started")
        print(f"  Browser will auto-open. If not, visit:")
        print(f"  http://{config.HOST}:{config.PORT}")
        print(f"  Press Ctrl+C to exit")
        print(f"{'=' * 50}\n")

    # Start server
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True
    )
