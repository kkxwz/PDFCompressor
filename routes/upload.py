"""
File Upload Routes
"""
import os
import uuid
from flask import Blueprint, Response, request, jsonify
from werkzeug.utils import secure_filename

import config
from security import RateLimiter, reject_rate_limited, security_logger
from utils import format_size

upload_bp = Blueprint("upload", __name__)

# Bounds abuse of the upload endpoint (disk exhaustion); per client IP
_upload_limiter = RateLimiter(config.RATE_LIMIT_UPLOAD,
                              config.RATE_LIMIT_WINDOW_SECONDS)

# Filenames are truncated in audit logs so hostile names cannot bloat them
_LOG_NAME_LIMIT = 80


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


@upload_bp.route("/api/upload", methods=["POST"])
def upload_file() -> tuple[Response, int]:
    """Upload PDF file"""
    if not _upload_limiter.allow(request.remote_addr or "unknown"):
        return reject_rate_limited("/api/upload", request.remote_addr)

    # Check if file exists in request
    if "file" not in request.files:
        return jsonify({
            "error": "NO_FILE",
            "message": "No file selected"
        }), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({
            "error": "NO_FILE",
            "message": "No file selected"
        }), 400

    # Check file type
    if not allowed_file(file.filename):
        security_logger.info(
            "Upload rejected (extension): %r from %s",
            file.filename[:_LOG_NAME_LIMIT], request.remote_addr,
        )
        return jsonify({
            "error": "ONLY_PDF",
            "message": "Only PDF format files are supported"
        }), 400

    # Check PDF magic bytes (rejects renamed non-PDF files)
    header = file.stream.read(5)
    file.stream.seek(0)
    if header != b"%PDF-":
        security_logger.info(
            "Upload rejected (magic bytes %r): %r from %s",
            header, file.filename[:_LOG_NAME_LIMIT], request.remote_addr,
        )
        return jsonify({
            "error": "ONLY_PDF",
            "message": "Only PDF format files are supported"
        }), 400

    # Generate unique file ID
    file_id = str(uuid.uuid4())
    original_filename = secure_filename(file.filename)
    if not original_filename:
        original_filename = "document.pdf"

    # Save file
    save_filename = f"{file_id}_{original_filename}"
    save_path = os.path.join(config.UPLOAD_FOLDER, save_filename)

    try:
        file.save(save_path)
    except Exception as e:
        return jsonify({
            "error": "SAVE_FAILED",
            "message": f"File save failed: {str(e)}"
        }), 500

    # Get file size
    file_size = os.path.getsize(save_path)

    # Check file size limit
    if file_size > config.MAX_CONTENT_LENGTH:
        os.remove(save_path)
        return jsonify({
            "error": "FILE_TOO_LARGE",
            "message": f"File too large ({format_size(file_size)}), max supported {format_size(config.MAX_CONTENT_LENGTH)}"
        }), 400

    return jsonify({
        "file_id": file_id,
        "filename": original_filename,
        "size": file_size,
        "size_human": format_size(file_size)
    }), 200
