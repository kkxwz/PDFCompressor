"""Tests for upload functionality."""
import os
from io import BytesIO

import pytest
from flask import Flask

import config
from routes.upload import upload_bp


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create test Flask app (isolated upload dir, no real-data pollution)."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(upload_dir))

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
    app.config["TESTING"] = True
    app.register_blueprint(upload_bp)
    yield app


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
        data={"file": (BytesIO(b""), "")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "NO_FILE"


def test_upload_invalid_extension(client):
    """Test upload with non-PDF file."""
    response = client.post(
        "/api/upload",
        data={"file": (BytesIO(b"test content"), "test.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"] == "ONLY_PDF"


def test_upload_fake_pdf_content(client):
    """Test upload with .pdf extension but non-PDF content (magic bytes check)."""
    response = client.post(
        "/api/upload",
        data={"file": (BytesIO(b"this is not a pdf"), "fake.pdf")},
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
        data={"file": (BytesIO(pdf_content), "test.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "file_id" in data
    assert data["filename"] == "test.pdf"
    assert data["size"] == len(pdf_content)
    assert data["size_human"] == f"{len(pdf_content)} B"


def test_upload_oversized_file(client):
    """Test upload with file exceeding size limit."""
    # Create a large fake PDF
    large_content = b"%PDF-1.4" + b"x" * (config.MAX_CONTENT_LENGTH + 1)
    response = client.post(
        "/api/upload",
        data={"file": (BytesIO(large_content), "large.pdf")},
        content_type="multipart/form-data",
    )
    # Flask should reject before our code runs due to MAX_CONTENT_LENGTH
    assert response.status_code in (400, 413)
