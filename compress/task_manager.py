"""
任务管理器 - 管理压缩任务的生命周期

支持：
- 异步执行压缩任务
- 进度追踪
- 任务状态查询
- 临时文件自动清理
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
    """压缩任务"""

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
        """更新进度（线程安全）"""
        self.progress = progress
        self.stage_message = message

    def to_dict(self) -> dict:
        """转换为字典"""
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
    """任务管理器"""

    def __init__(self, max_workers: int = 4):
        self.tasks: dict[str, Task] = {}
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 启动清理线程
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

    def create_task(self, file_id: str, input_path: str, level: str,
                    original_filename: str) -> Task:
        """创建压缩任务"""
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
        """异步启动压缩任务"""
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
                    task.stage_message = "压缩完成！"
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
                    task.error = result.get("error", "压缩失败")
                    logger.error(f"任务 {task.task_id} 失败: {task.error}")

            except Exception as e:
                task.status = TaskStatus.ERROR
                task.error = str(e)
                logger.exception(f"任务 {task.task_id} 异常")

        self.executor.submit(run_compression)

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)

    def _cleanup_loop(self):
        """定期清理过期任务和文件"""
        while True:
            time.sleep(60)  # 每分钟检查一次
            self._cleanup_expired()

    def _cleanup_expired(self):
        """清理过期任务"""
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
                    # 清理输出文件
                    if os.path.isfile(task.output_path):
                        try:
                            os.remove(task.output_path)
                            logger.info(f"已清理输出文件: {task.output_path}")
                        except Exception as e:
                            logger.warning(f"清理输出文件失败: {e}")

        if tasks_to_remove:
            logger.info(f"已清理 {len(tasks_to_remove)} 个过期任务")


# 全局任务管理器实例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取全局任务管理器"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
