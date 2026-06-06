"""
Task Manager - Manages compression task lifecycle

Supports:
- Async compression task execution
- Progress tracking
- Task status query
- Auto temp file cleanup
"""
import os
import uuid
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import config
from compress.engine import compress_pdf

logger = logging.getLogger(__name__)


class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class Task:
    """Compression task"""

    def __init__(self, task_id: str, file_id: str, input_path: str,
                 output_path: str, level: str, original_filename: str):
        self.task_id = task_id
        self.file_id = file_id
        self.input_path = input_path
        self.output_path = output_path
        self.level = level
        self.original_filename = original_filename

        self.status = TaskStatus.PENDING
        self.progress = 0
        self.stage_message = ""
        self.result = None
        self.error = None

        self.created_at = time.time()

    def update_progress(self, progress: int, message: str):
        """Update progress (thread-safe)"""
        self.progress = progress
        self.stage_message = message

    def to_dict(self) -> dict:
        """Convert to dict"""
        data = {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "stage_message": self.stage_message,
        }
        if self.result:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        return data


class TaskManager:
    """Task manager"""

    def __init__(self, max_workers: int = 4):
        self.tasks: dict[str, Task] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # Start cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

    def create_task(self, file_id: str, input_path: str, level: str,
                    original_filename: str) -> Task:
        """Create compression task"""
        task_id = str(uuid.uuid4())
        output_filename = f"{task_id}_compressed.pdf"
        output_path = os.path.join(config.OUTPUT_FOLDER, output_filename)

        task = Task(
            task_id=task_id,
            file_id=file_id,
            input_path=input_path,
            output_path=output_path,
            level=level,
            original_filename=original_filename
        )

        with self.lock:
            self.tasks[task_id] = task

        return task

    def start_task(self, task: Task):
        """Async start compression task"""
        task.status = TaskStatus.PROCESSING

        def run_compression():
            try:
                result = compress_pdf(
                    input_path=task.input_path,
                    output_path=task.output_path,
                    level=task.level,
                    progress_callback=task.update_progress
                )

                if result["success"]:
                    task.status = TaskStatus.DONE
                    task.progress = 100
                    task.stage_message = "Compression complete!"
                    task.result = {
                        "original_size": result["original_size"],
                        "compressed_size": result["compressed_size"],
                        "ratio": result["ratio"],
                        "download_url": f"/api/download/{task.task_id}"
                    }
                    if "warning" in result:
                        task.result["warning"] = result["warning"]
                else:
                    task.status = TaskStatus.ERROR
                    task.error = result.get("error", "Compression failed")
                    logger.error(f"Task {task.task_id} failed: {task.error}")

            except Exception as e:
                task.status = TaskStatus.ERROR
                task.error = str(e)
                logger.exception(f"Task {task.task_id} exception")

        self.executor.submit(run_compression)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task"""
        with self.lock:
            return self.tasks.get(task_id)

    def _cleanup_loop(self):
        """Periodic cleanup of expired tasks and files"""
        while True:
            time.sleep(60)  # Check every minute
            self._cleanup_expired()

    def _cleanup_expired(self):
        """Clean up expired tasks"""
        current_time = time.time()
        tasks_to_remove = []

        with self.lock:
            for task_id, task in self.tasks.items():
                age = current_time - task.created_at
                if age > config.FILE_CLEANUP_SECONDS:
                    tasks_to_remove.append(task_id)

            for task_id in tasks_to_remove:
                task = self.tasks.pop(task_id, None)
                if task:
                    # Clean up output file
                    if os.path.isfile(task.output_path):
                        try:
                            os.remove(task.output_path)
                            logger.info(f"Cleaned up output file: {task.output_path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up output file: {e}")

        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} expired tasks")


# Global task manager instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get global task manager"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
