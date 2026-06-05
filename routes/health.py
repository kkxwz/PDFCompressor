"""
健康检查路由 - 检测 Ghostscript 可用性
"""
from flask import Blueprint, jsonify

from compress.engine import find_ghostscript, get_gs_version

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health")
def health_check():
    """健康检查"""
    gs_path = find_ghostscript()
    gs_version = None

    if gs_path:
        gs_version = get_gs_version(gs_path)

    return jsonify({
        "status": "ok" if gs_path else "warning",
        "ghostscript": {
            "available": gs_path is not None,
            "path": gs_path,
            "version": gs_version
        },
        "message": "Ghostscript 已就绪" if gs_path else "未找到 Ghostscript，压缩功能不可用"
    })
