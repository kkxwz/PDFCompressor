"""
Health Check Routes - Detect Ghostscript availability
"""
from flask import Blueprint, jsonify

from compress.engine import find_ghostscript, get_gs_version

health_bp = Blueprint("health", __name__)


@health_bp.route("/api/health")
def health_check():
    """Health check"""
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
        "message": "Ghostscript ready" if gs_path else "Ghostscript not found, compression unavailable"
    })
