"""Tests for the compression task manager: lifecycle, result publishing and
the expiry cleanup rules (active tasks get a grace period)."""
import os
import time
from typing import Any, Callable, Optional

import pytest

import config
import compress.task_manager as tm_module
from compress.task_manager import TaskManager, TaskStatus

VALID_UUID_INPUT = "12345678-1234-1234-1234-123456789abc_doc.pdf"


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(config, "UPLOAD_FOLDER", str(upload_dir))
    monkeypatch.setattr(config, "OUTPUT_FOLDER", str(output_dir))


def _make_manager(monkeypatch: pytest.MonkeyPatch,
                  result: Optional[dict[str, Any]] = None) -> TaskManager:
    """TaskManager whose compression step is mocked. The mocked engine
    writes the output file like the real gs would."""
    if result is None:
        result = {"success": True, "original_size": 1000,
                  "compressed_size": 500, "ratio": 50.0}

    def fake_compress(input_path: str, output_path: str, level: str,
                      progress_callback: Optional[Callable[[int, str], None]] = None,
                      timeout: Optional[int] = None) -> dict[str, Any]:
        if result["success"]:
            with open(output_path, "wb") as f:
                f.write(b"pdf")
            if progress_callback:
                progress_callback(100, "Compression complete!")
        return result

    monkeypatch.setattr(tm_module, "compress_pdf", fake_compress)
    return TaskManager(max_workers=2)


def _start_input_file() -> str:
    path = os.path.join(config.UPLOAD_FOLDER, VALID_UUID_INPUT)
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4")
    return path


def _wait_status(manager: TaskManager, task_id: str,
                 expected: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = manager.get_task(task_id)
        if task and task.status == expected:
            return
        time.sleep(0.01)
    task = manager.get_task(task_id)
    raise AssertionError(
        f"task {task_id} stuck at {task.status if task else None}, "
        f"expected {expected}")


# ---------- creation & lookup ----------

def test_create_task_layout(isolated_dirs):
    manager = TaskManager(max_workers=1)
    task = manager.create_task(
        file_id="fid", input_path="/in.pdf", level="medium",
        original_filename="doc.pdf")

    assert manager.get_task(task.task_id) is task
    assert task.status == TaskStatus.PENDING
    assert task.output_path == os.path.join(
        config.OUTPUT_FOLDER, f"{task.task_id}_compressed.pdf")
    assert manager.get_task("nope") is None


# ---------- success lifecycle ----------

def test_task_success_publishes_result_and_removes_input(monkeypatch, isolated_dirs):
    manager = _make_manager(monkeypatch)
    input_path = _start_input_file()
    task = manager.create_task(
        file_id="fid", input_path=input_path, level="medium",
        original_filename="doc.pdf")

    manager.start_task(task)
    _wait_status(manager, task.task_id, TaskStatus.DONE)

    assert task.progress == 100
    assert task.result["compressed_size"] == 500
    assert task.result["download_url"] == f"/api/download/{task.task_id}"
    assert os.path.isfile(task.output_path)
    # Input file must be cleaned up after compression
    assert not os.path.isfile(input_path)


def test_task_error_surfaces_engine_message(monkeypatch, isolated_dirs):
    manager = _make_manager(
        monkeypatch, result={"success": False, "error": "gs exploded"})
    task = manager.create_task(
        file_id="fid", input_path=_start_input_file(), level="high",
        original_filename="doc.pdf")

    manager.start_task(task)
    _wait_status(manager, task.task_id, TaskStatus.ERROR)

    assert task.error == "gs exploded"
    assert task.result is None


def test_task_exception_recorded(monkeypatch, isolated_dirs):
    """An unexpected exception inside the worker must not kill the pool."""
    def boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(tm_module, "compress_pdf", boom)
    manager = TaskManager(max_workers=1)
    task = manager.create_task(
        file_id="fid", input_path=_start_input_file(), level="low",
        original_filename="doc.pdf")

    manager.start_task(task)
    _wait_status(manager, task.task_id, TaskStatus.ERROR)
    assert "kaboom" in (task.error or "")


# ---------- cleanup rules ----------

def test_cleanup_removes_expired_done_task_and_output(monkeypatch, isolated_dirs):
    manager = _make_manager(monkeypatch)
    task = manager.create_task(
        file_id="fid", input_path=_start_input_file(), level="medium",
        original_filename="doc.pdf")
    task.status = TaskStatus.DONE
    with open(task.output_path, "wb") as f:
        f.write(b"pdf")
    # Age it past the cleanup threshold
    task.created_at = time.time() - config.FILE_CLEANUP_SECONDS - 1

    manager._cleanup_expired()

    assert manager.get_task(task.task_id) is None
    assert not os.path.isfile(task.output_path)


def test_cleanup_keeps_young_done_task(monkeypatch, isolated_dirs):
    manager = _make_manager(monkeypatch)
    task = manager.create_task(
        file_id="fid", input_path=_start_input_file(), level="medium",
        original_filename="doc.pdf")
    task.status = TaskStatus.DONE  # created just now

    manager._cleanup_expired()
    assert manager.get_task(task.task_id) is task


def test_cleanup_grace_period_for_processing_task(monkeypatch, isolated_dirs):
    """A stuck PROCESSING task survives the normal cleanup window and is
    only reclaimed after the extra compression-timeout grace period."""
    manager = _make_manager(monkeypatch)
    task = manager.create_task(
        file_id="fid", input_path=_start_input_file(), level="medium",
        original_filename="doc.pdf")
    task.status = TaskStatus.PROCESSING
    stale_seconds = config.FILE_CLEANUP_SECONDS + config.COMPRESS_TIMEOUT

    # Past the normal window but inside the grace period -> kept
    task.created_at = time.time() - config.FILE_CLEANUP_SECONDS - 10
    manager._cleanup_expired()
    assert manager.get_task(task.task_id) is task

    # Past the grace period -> reclaimed
    task.created_at = time.time() - stale_seconds - 1
    manager._cleanup_expired()
    assert manager.get_task(task.task_id) is None
