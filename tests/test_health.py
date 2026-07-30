"""Tests for health check route (Ghostscript probe caching)."""
import pytest
from flask import Flask

import config
import routes.health as health_module
from routes.health import health_bp


@pytest.fixture
def app(monkeypatch):
    """Create test Flask app with a reset probe cache."""
    monkeypatch.setattr(health_module, "_probe_cache", None)
    monkeypatch.setattr(health_module, "_probe_failed_at", 0.0)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(health_bp)
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_health_reports_version_and_gs(client, monkeypatch):
    """Health returns app version and Ghostscript info."""
    monkeypatch.setattr(health_module, "find_ghostscript", lambda: "/usr/bin/gs")
    monkeypatch.setattr(health_module, "get_gs_version", lambda path: "10.0")

    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["version"] == config.VERSION
    assert data["ghostscript"]["available"] is True
    assert data["ghostscript"]["path"] == "/usr/bin/gs"
    assert data["ghostscript"]["version"] == "10.0"


def test_health_probe_cached_after_success(client, monkeypatch):
    """A successful probe must not re-run find/version on later requests."""
    calls = {"find": 0, "version": 0}

    def fake_find():
        calls["find"] += 1
        return "/usr/bin/gs"

    def fake_version(path):
        calls["version"] += 1
        return "10.0"

    monkeypatch.setattr(health_module, "find_ghostscript", fake_find)
    monkeypatch.setattr(health_module, "get_gs_version", fake_version)

    for _ in range(3):
        assert client.get("/api/health").status_code == 200

    assert calls["find"] == 1
    assert calls["version"] == 1


def test_health_failed_probe_not_hammered(client, monkeypatch):
    """A failed probe is cached for a short TTL (no probe storm)."""
    calls = {"find": 0}

    def fake_find():
        calls["find"] += 1
        return None

    monkeypatch.setattr(health_module, "find_ghostscript", fake_find)

    for _ in range(3):
        response = client.get("/api/health")
        assert response.get_json()["status"] == "warning"

    assert calls["find"] == 1
