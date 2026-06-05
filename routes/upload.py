"""
文件上传路由
"""
import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

import config

upload_bp = Blueprint("upload", __name__)


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否允许"""
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
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
    """上传 PDF 文件"""
    # 检查是否有文件
    if "file" not in request.files:
        return jsonify({
            "error": "NO_FILE",
            "message": "未选择文件"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "error": "NO_FILE",
            "message": "未选择文件"
        }), 400

    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify({
            "error": "ONLY_PDF",
            "message": "仅支持 PDF 格式文件"
        }), 400

    # 生成唯一文件 ID
    file_id = str(uuid.uuid4())
    original_filename = secure_filename(file.filename)
    if not original_filename:
        original_filename = "document.pdf"

    # 保存文件
    save_filename = f"{file_id}_{original_filename}"
    save_path = os.path.join(config.UPLOAD_FOLDER, save_filename)

    try:
        file.save(save_path)
    except Exception as e:
        return jsonify({
            "error": "SAVE_FAILED",
            "message": f"文件保存失败: {str(e)}"
        }), 500

    # 获取文件大小
    file_size = os.path.getsize(save_path)

    # 检查文件大小限制
    if file_size > config.MAX_CONTENT_LENGTH:
        os.remove(save_path)
        return jsonify({
            "error": "FILE_TOO_LARGE",
            "message": f"文件过大（{format_size(file_size)}），最大支持 {format_size(config.MAX_CONTENT_LENGTH)}"
        }), 400

    return jsonify({
        "file_id": file_id,
        "filename": original_filename,
        "size": file_size,
        "size_human": format_size(file_size)
    }), 200
