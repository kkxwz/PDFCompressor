"""
Security Middleware - CSRF protection, rate limiting, audit logging

Design notes:
- CSRF: the app ships no cookies/sessions, so the classic "custom request
  header" guard is used. HTML forms cannot set custom headers, and a
  cross-origin fetch/XHR with a custom header triggers a CORS preflight that
  this server never allows (no CORS headers are emitted) - therefore a
  malicious web page cannot forge state-changing POSTs against the local
  server. The frontend attaches `X-Requested-With: XMLHttpRequest` to every
  fetch call.
- Rate limiting: fixed-window, in-memory, keyed by (endpoint, client IP).
  Bounds abuse of the upload/compress endpoints (disk + CPU exhaustion);
  state resets on restart, which is acceptable for a single-user local app.
- Audit logging: all security-relevant rejections go through the dedicated
  `slimpdf.security` logger so anomalous behaviour is easy to grep out of
  the rotating log file.
"""
import logging
import threading
import time
from typing import Optional

from flask import Request, jsonify, Response

security_logger = logging.getLogger("slimpdf.security")

# Custom header every state-changing request must carry (see module docstring)
CSRF_HEADER = "X-Requested-With"
CSRF_HEADER_EXPECTED = "XMLHttpRequest"

# Methods that mutate state and therefore require the CSRF header
_PROTECTED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def check_csrf(request: Request) -> Optional[tuple[Response, int]]:
    """Return a 403 response tuple if the request fails the CSRF guard,
    otherwise None. Intended for use as a before_request hook."""
    if request.method not in _PROTECTED_METHODS:
        return None
    if request.headers.get(CSRF_HEADER) == CSRF_HEADER_EXPECTED:
        return None

    security_logger.warning(
        "CSRF check failed: %s %s without %s header from %s",
        request.method, request.path, CSRF_HEADER, request.remote_addr,
    )
    return jsonify({
        "error": "CSRF_REJECTED",
        "message": "Request rejected: missing or invalid request header"
    }), 403


class RateLimiter:
    """Thread-safe fixed-window rate limiter (per key)"""

    def __init__(self, limit: int, window_seconds: float = 60.0):
        self.limit = limit
        self.window = window_seconds
        self._counts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record one request for `key`; return False when over the limit"""
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            hits = [t for t in self._counts.get(key, ()) if t > cutoff]
            if len(hits) >= self.limit:
                self._counts[key] = hits
                return False
            hits.append(now)
            self._counts[key] = hits
            return True


def reject_rate_limited(endpoint: str, client_addr: Optional[str]) -> tuple[Response, int]:
    """Build the 429 response and record the abuse attempt"""
    security_logger.warning(
        "Rate limit exceeded on %s from %s", endpoint, client_addr,
    )
    return jsonify({
        "error": "RATE_LIMITED",
        "message": "Too many requests, please slow down and retry"
    }), 429
