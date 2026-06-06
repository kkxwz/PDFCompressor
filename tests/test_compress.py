"""Tests for compression routes."""
import json
import os
import pytest
from flask import Flask
from unittest.mock import patch, MagicMock

import config
from routes.compress import compress_bp
from routes.upload import upload_bp
from compress.task_manager import TaskStatus


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(upload_bp)
    app.register_blueprint(compress_bp)
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)
    yield app
    # Cleanup
    for folder in [config.UPLOAD_FOLDER, config.OUTPUT_FOLDER]:
        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                pass


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
