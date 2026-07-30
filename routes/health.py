"""
Health Check Routes - Detect Ghostscript availability

The Ghostscript probe (filesystem lookup + subprocess for version) is cached:
a successful probe is kept for the process lifetime (the bundled/system gs
does not change while running), a failed probe is retried after a short TTL
so a freshly installed gs is picked up without restarting.
"""
import threading
import time
from typing import Optional

from flask import Blueprint, Response, jsonify

import config
from compress.engine import find_ghostscript, get_gs_version

health_bp = Blueprint("health", __name__)

# Retry interval after a failed probe (seconds)
_FAILED_PROBE_TTL = 30.0

_probe_lock = threading.Lock()
_probe_cache: Optional[tuple[Optional[str], Optional[str]]] = None
_probe_failed_at: float = 0.0


def _probe_ghostscript() -> tuple[Optional[str], Optional[str]]:
    """Return (gs_path, gs_version), cached (see module docstring)"""
    global _probe_cache, _probe_failed_at

    with _probe_lock:
        if _probe_cache is not None:
            return _probe_cache
        if time.time() - _probe_failed_at < _FAILED_PROBE_TTL:
            return None, None

        gs_path = find_ghostscript()
        gs_version = get_gs_version(gs_path) if gs_path else None

        if gs_path:
            _probe_cache = (gs_path, gs_version)
        else:
            _probe_failed_at = time.time()
        return gs_path, gs_version


@health_bp.route("/api/health")
def health_check() -> Response:
    """Health check"""
    gs_path, gs_version = _probe_ghostscript()

    return jsonify({
        "status": "ok" if gs_path else "warning",
        "version": config.VERSION,
        "ghostscript": {
            "available": gs_path is not None,
            "path": gs_path,
            "version": gs_version
        },
        "message": "Ghostscript ready" if gs_path else "Ghostscript not found, compression unavailable"
    })
