"""Tests for compression engine."""
import os
import pytest
from unittest.mock import patch, MagicMock

from compress.engine import (
    _validate_pdf_path,
    _build_gs_command,
    _parse_progress,
    find_ghostscript,
)
import config


class TestValidatePdfPath:
    """Tests for _validate_pdf_path."""

    def test_valid_upload_path(self, tmp_path):
        """Test valid path in upload folder."""
        # Create a temp file in upload folder
        test_file = os.path.join(config.UPLOAD_FOLDER, "test.pdf")
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        with open(test_file, "w") as f:
            f.write("test")
        assert _validate_pdf_path(test_file) is True
        os.remove(test_file)

    def test_invalid_extension(self, tmp_path):
        """Test file without .pdf extension."""
        test_file = os.path.join(config.UPLOAD_FOLDER, "test.txt")
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        with open(test_file, "w") as f:
            f.write("test")
        assert _validate_pdf_path(test_file) is False
        os.remove(test_file)

    def test_path_traversal(self, tmp_path):
        """Test path traversal attack."""
        malicious_path = "/etc/passwd"
        assert _validate_pdf_path(malicious_path) is False

    def test_nonexistent_file(self):
        """Test non-existent file."""
        assert _validate_pdf_path("/tmp/nonexistent.pdf") is False


class TestBuildGsCommand:
    """Tests for _build_gs_command."""

    def test_basic_command_structure(self):
        """Test basic command structure."""
        profile = {
            "compatibility_level": "1.5",
            "DownsampleColorImages": True,
            "ColorImageResolution": 150,
        }
        cmd = _build_gs_command("/usr/bin/gs", "/tmp/in.pdf", "/tmp/out.pdf", profile)
        assert cmd[0] == "/usr/bin/gs"
        assert "-sDEVICE=pdfwrite" in cmd
        assert "-dCompatibilityLevel=1.5" in cmd
        assert "-dNOPAUSE" in cmd
        assert "-dBATCH" in cmd
        assert "-dSAFER" in cmd
        assert "-sOutputFile=/tmp/out.pdf" in cmd
        assert "-f" in cmd
        assert "/tmp/in.pdf" in cmd

    def test_boolean_params(self):
        """Test boolean parameter conversion."""
        profile = {"DownsampleColorImages": True}
        cmd = _build_gs_command("gs", "in.pdf", "out.pdf", profile)
        assert "-dDownsampleColorImages=true" in cmd

    def test_integer_params(self):
        """Test integer parameter conversion."""
        profile = {"ColorImageResolution": 150}
        cmd = _build_gs_command("gs", "in.pdf", "out.pdf", profile)
        assert "-dColorImageResolution=150" in cmd


class TestParseProgress:
    """Tests for _parse_progress."""

    def test_total_pages_detection(self):
        """Test total pages line parsing."""
        result = _parse_progress("Processing pages 1 through 12.", 0)
        assert result == 0

    def test_page_progress(self):
        """Test page progress calculation."""
        result = _parse_progress("Page 6", 12)
        assert result == 50

    def test_no_match(self):
        """Test line with no progress info."""
        result = _parse_progress("Some random output", 12)
        assert result is None


class TestFindGhostscript:
    """Tests for find_ghostscript."""

    @patch("compress.engine.shutil.which")
    @patch("os.path.isfile")
    @patch("os.access")
    def test_find_in_path(self, mock_access, mock_isfile, mock_which):
        """Test finding gs in PATH."""
        mock_which.return_value = "/usr/bin/gs"
        mock_isfile.return_value = True
        mock_access.return_value = True
        result = find_ghostscript()
        assert result == "/usr/bin/gs"

    @patch("compress.engine.shutil.which")
    def test_not_found(self, mock_which):
        """Test when gs is not found."""
        mock_which.return_value = None
        result = find_ghostscript()
        assert result is None
