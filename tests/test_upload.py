"""Tests for upload functionality."""
import os
import tempfile
import pytest
from flask import Flask

import config
from routes.upload import upload_bp


@pytest.fixture
def app():
    """Create test Flask app."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config["TESTING"] = True
    app.register_blueprint(upload_bp)
    # Ensure upload directory exists
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    yield app
    # Cleanup
    for f in os.listdir(config.UPLOAD_FOLDER):
        try:
            os.remove(os.path.join(config.UPLOAD_FOLDER, f))
        except OSError:
            pass


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_upload_no_file(client):
    """Test upload without file."""
    response = client.post("/api/upload")
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "NO_FILE"


def test_upload_empty_filename(client):
    """Test upload with empty filename."""
    response = client.post(
        "/api/upload",
        data={"file": (b"", "")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "NO_FILE"


def test_upload_invalid_extension(client):
    """Test upload with non-PDF file."""
    response = client.post(
        "/api/upload",
        data={"file": (b"test content", "test.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "ONLY_PDF"


def test_upload_valid_pdf(client):
    """Test upload with valid PDF file."""
    pdf_content = b"%PDF-1.4 test content"
    response = client.post(
        "/api/upload",
        data={"file": (pdf_content, "test.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "file_id" in data
    assert data["filename"] == "test.pdf"
    assert data["size"] == len(pdf_content)
    assert data["size_human"] == "19.0 B"


def test_upload_oversized_file(client):
    """Test upload with file exceeding size limit."""
    # Create a large fake PDF
    large_content = b"%PDF-1.4" + b"x" * (config.MAX_CONTENT_LENGTH + 1)
    response = client.post(
        "/api/upload",
        data={"file": (large_content, "large.pdf")},
        content_type="multipart/form-data",
    )
    # Flask should reject before our code runs due to MAX_CONTENT_LENGTH
    assert response.status_code in (400, 413)
