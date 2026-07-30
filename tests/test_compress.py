"""Tests for compression routes."""
import json
import os
import pytest
from flask import Flask

import config
from routes.compress import compress_bp, _find_upload_file
from routes.upload import upload_bp
from compress.task_manager import TaskStatus


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create test Flask app (isolated dirs, no real-data pollution)."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(upload_dir))
    monkeypatch.setattr(config, "OUTPUT_FOLDER", str(output_dir))

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(upload_bp)
    app.register_blueprint(compress_bp)
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_compress_missing_file_id(client):
    """Test compression without file_id."""
    response = client.post(
        "/api/compress",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "MISSING_FILE_ID"


def test_compress_invalid_level(client):
    """Test compression with invalid level."""
    response = client.post(
        "/api/compress",
        data=json.dumps({"file_id": "test", "level": "invalid"}),
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "INVALID_LEVEL"


def test_compress_file_not_found(client):
    """Test compression with non-existent file."""
    response = client.post(
        "/api/compress",
        data=json.dumps({"file_id": "nonexistent", "level": "medium"}),
        content_type="application/json",
    )
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "FILE_NOT_FOUND"


def test_download_task_not_found(client):
    """Test download with non-existent task."""
    response = client.get("/api/download/nonexistent-task")
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "TASK_NOT_FOUND"


def test_find_upload_file_rejects_glob_injection(app):
    """file_id with glob wildcards must not match any uploaded file."""
    # Place a legitimately named upload in the folder
    victim = os.path.join(config.UPLOAD_FOLDER,
                          "12345678-1234-1234-1234-123456789abc_doc.pdf")
    with open(victim, "wb") as f:
        f.write(b"%PDF-1.4")

    for malicious_id in ("*", "?", "[!a]", "../../etc", "12345678*"):
        path, name = _find_upload_file(malicious_id)
        assert path is None
        assert name is None

    # A well-formed uuid still resolves normally
    path, name = _find_upload_file("12345678-1234-1234-1234-123456789abc")
    assert path == victim
    assert name == "doc.pdf"
