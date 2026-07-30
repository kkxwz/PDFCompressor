"""Tests for shared utilities."""
from utils import format_size


def test_format_size_bytes():
    assert format_size(0) == "0 B"
    assert format_size(1023) == "1023 B"


def test_format_size_kb():
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"


def test_format_size_mb():
    assert format_size(20 * 1024 * 1024) == "20.0 MB"


def test_format_size_gb():
    assert format_size(2 * 1024 * 1024 * 1024) == "2.00 GB"
