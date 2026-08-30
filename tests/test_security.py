"""Tests for security hardening: CSRF guard, security headers, rate limiting,
malformed task_id rejection."""
import time
from io import BytesIO

import pytest

import app as app_module
import config
from security import RateLimiter, check_csrf

CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Full app via create_app() (so before/after request hooks are active),
    with isolated upload/output dirs and relaxed rate limits."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(upload_dir))
    monkeypatch.setattr(config, "OUTPUT_FOLDER", str(output_dir))

    application = app_module.create_app()
    application.config["TESTING"] = True

    # Reset module-level limiter state and loosen limits for test speed
    from routes import upload as upload_routes
    from routes import compress as compress_routes
    monkeypatch.setattr(
        upload_routes, "_upload_limiter", RateLimiter(1000, 60.0))
    monkeypatch.setattr(
        compress_routes, "_compress_limiter", RateLimiter(1000, 60.0))
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


# ---------- CSRF guard ----------

def test_post_without_csrf_header_rejected(client):
    """A state-changing request without the custom header is a CSRF suspect."""
    response = client.post("/api/upload")
    assert response.status_code == 403
    assert response.get_json()["error"] == "CSRF_REJECTED"


def test_post_with_csrf_header_passes_guard(client):
    """With the header the request reaches normal validation (NO_FILE)."""
    response = client.post("/api/upload", headers=CSRF_HEADERS)
    assert response.status_code == 400
    assert response.get_json()["error"] == "NO_FILE"


def test_get_not_subject_to_csrf(client):
    """Read-only routes must keep working without the header."""
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_check_csrf_ignores_get():
    """Unit-level: GET/HEAD bypass the guard entirely."""
    from werkzeug.test import EnvironBuilder
    from werkzeug.wrappers import Request

    for method in ("GET", "HEAD"):
        request = Request(EnvironBuilder(method=method).get_environ())
        assert check_csrf(request) is None


# ---------- Security response headers ----------

def test_security_headers_present(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


# ---------- Rate limiting ----------

def test_rate_limiter_unit():
    limiter = RateLimiter(limit=2, window_seconds=60.0)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False
    # A different key has its own budget
    assert limiter.allow("other") is True


def test_rate_limiter_window_expiry(monkeypatch):
    limiter = RateLimiter(limit=1, window_seconds=1.0)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False

    # Shift the clock past the window: the slot must free up
    fake_time = {"now": time.time()}
    monkeypatch.setattr("security.time.time", lambda: fake_time["now"])
    fake_time["now"] += 2.0
    assert limiter.allow("k") is True


def test_upload_rate_limit_returns_429(app, client, monkeypatch):
    from routes import upload as upload_routes
    monkeypatch.setattr(
        upload_routes, "_upload_limiter", RateLimiter(2, 60.0))

    for _ in range(2):
        response = client.post("/api/upload", headers=CSRF_HEADERS)
        assert response.status_code == 400  # NO_FILE, but counted

    response = client.post("/api/upload", headers=CSRF_HEADERS)
    assert response.status_code == 429
    assert response.get_json()["error"] == "RATE_LIMITED"


# ---------- Malformed task_id rejection ----------

def test_download_malformed_task_id_rejected(client):
    """task_id must be a uuid4; anything else 404s without dict lookups."""
    for bad in ("*", "abc", "12345678",
                "12345678-1234-1234-1234-123456789abcZ",  # uppercase fails
                "12345678-1234-1234-1234-123456789ab"):
        response = client.get(f"/api/download/{bad}")
        assert response.status_code == 404
        assert response.get_json()["error"] == "TASK_NOT_FOUND"


def test_progress_malformed_task_id_rejected(client):
    response = client.get("/api/progress/not-a-task")
    assert response.status_code == 404
    assert response.get_json()["error"] == "TASK_NOT_FOUND"


def test_download_wellformed_uuid_not_found(client):
    """A valid-format uuid that is not a real task still 404s (not crash)."""
    response = client.get(
        "/api/download/12345678-1234-1234-1234-123456789abc")
    assert response.status_code == 404


# ---------- Private directories ----------

def test_upload_full_flow_with_csrf_header(client):
    """Happy path: upload still succeeds with the CSRF header attached."""
    response = client.post(
        "/api/upload",
        headers=CSRF_HEADERS,
        data={"file": (BytesIO(b"%PDF-1.4 test"), "test.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert "file_id" in response.get_json()
