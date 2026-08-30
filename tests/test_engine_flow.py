"""Tests for the compress_pdf main flow and helpers.

Ghostscript is fully mocked: find_ghostscript points at a fake binary and a
FakePopen simulates gs behaviour (progress lines, exit codes, timeouts,
writing the output file) so the real engine logic - command building,
progress parsing, validation, error branches - is exercised end to end.
"""
import os
import subprocess
from typing import Any, Callable, Optional

import pytest

import config
import compress.engine as engine
from compress.engine import compress_pdf, _get_total_pages

FAKE_GS = "/fake/bin/gs"
VALID_UUID_INPUT = "12345678-1234-1234-1234-123456789abc_doc.pdf"


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Isolated upload/output dirs + fake Ghostscript discovery."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(upload_dir))
    monkeypatch.setattr(config, "OUTPUT_FOLDER", str(output_dir))
    monkeypatch.setattr(config, "GS_PATHS", [FAKE_GS])
    # Default: gs present; individual tests can override
    monkeypatch.setattr(engine, "find_ghostscript", lambda: FAKE_GS)
    # Skip the real page-count subprocess by default
    monkeypatch.setattr(engine, "_get_total_pages", lambda gs, path: 2)
    return {"upload": upload_dir, "output": output_dir}


def _make_input(path: str, size: int = 1000) -> str:
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4" + b"x" * size)
    return path


class FakePopen:
    """Minimal subprocess.Popen stand-in for Ghostscript.

    Configurable via class attributes (set per-test):
      lines: stdout lines to emit
      returncode: exit code after wait()
      timeout: raise TimeoutExpired from wait() when True
      output_size: bytes written to -sOutputFile (None = write nothing)
    """
    lines: list[str] = ["Processing pages 1 through 2.", "Page 1", "Page 2"]
    returncode = 0
    timeout = False
    output_size: Optional[int] = 500
    killed = False

    def __init__(self, cmd: list[str], **kwargs: Any):
        self.cmd = cmd
        self.stdout = iter(self.lines)
        self.returncode: Optional[int] = None

    def wait(self, timeout: Optional[float] = None) -> int:
        if self.timeout and not FakePopen.killed:
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        if self.returncode is None:
            self.returncode = FakePopen.returncode
            self._write_output()
        return self.returncode

    def _write_output(self) -> None:
        if FakePopen.output_size is None:
            return
        for arg in self.cmd:
            if arg.startswith("-sOutputFile="):
                out = arg[len("-sOutputFile="):]
                with open(out, "wb") as f:
                    f.write(b"y" * FakePopen.output_size)

    def kill(self) -> None:
        FakePopen.killed = True

    def join(self, timeout: Optional[float] = None) -> None:
        pass


@pytest.fixture
def fake_popen(monkeypatch):
    """Install a pristine FakePopen and return the class for tuning."""
    # Reset per-test state on the class itself
    FakePopen.lines = ["Processing pages 1 through 2.", "Page 1", "Page 2"]
    FakePopen.returncode = 0
    FakePopen.timeout = False
    FakePopen.output_size = 500
    FakePopen.killed = False
    monkeypatch.setattr(engine.subprocess, "Popen", FakePopen)
    return FakePopen


def _paths(dirs: dict[str, Any]) -> tuple[str, str]:
    input_path = os.path.join(config.UPLOAD_FOLDER, VALID_UUID_INPUT)
    output_path = os.path.join(config.OUTPUT_FOLDER, "out.pdf")
    return input_path, output_path


# ---------- success & fallback ----------

def test_compress_success(fake_popen, isolated_dirs):
    input_path, output_path = _paths(isolated_dirs)
    _make_input(input_path, size=1000)

    progress_calls: list[tuple[int, str, Optional[dict[str, Any]]]] = []
    result = compress_pdf(
        input_path, output_path, level="medium",
        progress_callback=lambda p, m, meta=None: progress_calls.append((p, m, meta)),
    )

    assert result["success"] is True
    assert result["original_size"] > result["compressed_size"]
    assert result["ratio"] > 0
    assert os.path.isfile(output_path)
    # Progress reaches completion, with the structured meta contract
    assert progress_calls[-1] == (
        100, "Compression complete!", {"key": "complete"})
    # Page events carry machine-readable counters for localization
    page_events = [meta for _, _, meta in progress_calls
                   if meta and meta.get("key") == "page"]
    assert page_events and page_events[0]["total"] == 2


def test_compress_fallback_when_output_larger(fake_popen, isolated_dirs):
    """If gs output is not smaller, the original is copied back."""
    input_path, output_path = _paths(isolated_dirs)
    _make_input(input_path, size=100)
    FakePopen.output_size = 5000  # "compressed" is bigger

    progress_calls: list[tuple[int, str, Optional[dict[str, Any]]]] = []
    result = compress_pdf(
        input_path, output_path, level="high",
        progress_callback=lambda p, m, meta=None: progress_calls.append((p, m, meta)),
    )

    assert result["success"] is True
    assert result["ratio"] == 0.0
    assert "warning" in result
    assert result["compressed_size"] == result["original_size"]
    # Early-return branch must still emit the completion stage
    assert progress_calls[-1] == (
        100, "Compression complete!", {"key": "complete"})
    # Output content must be the original file (copy fallback)
    with open(input_path, "rb") as f:
        original = f.read()
    with open(output_path, "rb") as f:
        assert f.read() == original


# ---------- error branches ----------

def test_compress_ghostscript_not_found(monkeypatch, isolated_dirs):
    monkeypatch.setattr(engine, "find_ghostscript", lambda: None)
    input_path, output_path = _paths(isolated_dirs)
    _make_input(input_path)

    result = compress_pdf(input_path, output_path)
    assert result["success"] is False
    assert "Ghostscript not found" in result["error"]


def test_compress_input_missing(isolated_dirs):
    input_path, output_path = _paths(isolated_dirs)  # not created
    result = compress_pdf(input_path, output_path)
    assert result["success"] is False
    assert "not found" in result["error"]


def test_compress_input_outside_upload_dir(tmp_path, isolated_dirs):
    """Path traversal input must be rejected by _validate_pdf_path."""
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4 evil")
    _, output_path = _paths(isolated_dirs)

    result = compress_pdf(str(outside), output_path)
    assert result["success"] is False
    assert result["error"] == "Invalid file path"


def test_compress_output_outside_output_dir(isolated_dirs):
    input_path, _ = _paths(isolated_dirs)
    _make_input(input_path)

    result = compress_pdf(input_path, "/tmp/evil_out.pdf")
    assert result["success"] is False
    assert result["error"] == "Invalid output path"


def test_compress_timeout_kills_process(fake_popen, isolated_dirs):
    input_path, output_path = _paths(isolated_dirs)
    _make_input(input_path)
    FakePopen.timeout = True

    result = compress_pdf(input_path, output_path, timeout=1)
    assert result["success"] is False
    assert "timed out" in result["error"]
    assert FakePopen.killed is True


def test_compress_nonzero_exit_reports_tail(fake_popen, isolated_dirs):
    input_path, output_path = _paths(isolated_dirs)
    _make_input(input_path)
    FakePopen.returncode = 1
    FakePopen.output_size = None
    FakePopen.lines = ["some warning", "Error: /invalidfont in findfont"]

    result = compress_pdf(input_path, output_path)
    assert result["success"] is False
    assert "code=1" in result["error"]
    assert "invalidfont" in result["error"]


def test_compress_no_output_generated(fake_popen, isolated_dirs):
    """gs exits 0 but writes nothing -> treated as failure."""
    input_path, output_path = _paths(isolated_dirs)
    _make_input(input_path)
    FakePopen.output_size = None

    result = compress_pdf(input_path, output_path)
    assert result["success"] is False
    assert "no output file" in result["error"]


# ---------- page count helper ----------

def test_get_total_pages_parses_stdout(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="12\n", stderr="")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    assert _get_total_pages(FAKE_GS, "/some/file.pdf") == 12
    # Sandbox flags must be present on the probe command
    assert "-dSAFER" in captured["cmd"]
    assert "--permit-file-read=/some/file.pdf" in captured["cmd"]


def test_get_total_pages_failure_returns_zero(monkeypatch):
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    assert _get_total_pages(FAKE_GS, "/some/file.pdf") == 0
