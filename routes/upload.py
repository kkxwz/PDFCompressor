"""
File Upload Routes
"""
import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

import config

upload_bp = Blueprint("upload", __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


def format_size(size_bytes: int) -> str:
    """Format file size"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@upload_bp.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload PDF file"""
    # Check if file exists in request
    if "file" not in request.files:
        return jsonify({
            "error": "NO_FILE",
            "message": "No file selected"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "error": "NO_FILE",
            "message": "No file selected"
        }), 400

    # Check file type
    if not allowed_file(file.filename):
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
