"""
压缩任务路由 - 启动压缩、进度推送、下载结果
"""
import os
import json
import time
import glob
from flask import Blueprint, request, jsonify, Response, send_file, stream_with_context

import config
from compress.task_manager import get_task_manager, TaskStatus

compress_bp = Blueprint("compress", __name__)


def _find_upload_file(file_id: str) -> tuple:
    """根据 file_id 查找上传的文件，返回 (文件路径, 原始文件名)"""
    pattern = os.path.join(config.UPLOAD_FOLDER, f"{file_id}_*.pdf")
    matches = glob.glob(pattern)
    if not matches:
        return None, None

    file_path = matches[0]
    # 提取原始文件名（去掉 file_id_ 前缀）
    basename = os.path.basename(file_path)
    original_filename = basename[len(file_id) + 1:]  # +1 for underscore
    return file_path, original_filename


@compress_bp.route("/api/compress", methods=["POST"])
def start_compress():
    """启动压缩任务"""
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "INVALID_REQUEST",
            "message": "请求数据无效"
        }), 400

    file_id = data.get("file_id")
    level = data.get("level", "medium")

    if not file_id:
        return jsonify({
            "error": "MISSING_FILE_ID",
            "message": "缺少 file_id"
        }), 400

    if level not in ("low", "medium", "high"):
        return jsonify({
            "error": "INVALID_LEVEL",
            "message": "无效的压缩级别，可选: low, medium, high"
        }), 400

    # 查找上传的文件
    input_path, original_filename = _find_upload_file(file_id)
    if not input_path:
        return jsonify({
            "error": "FILE_NOT_FOUND",
            "message": "未找到上传的文件，请重新上传"
        }), 404

    # 创建并启动任务
    task_manager = get_task_manager()
    task = task_manager.create_task(
        file_id=file_id,
        input_path=input_path,
        level=level,
        original_filename=original_filename
    )
    task_manager.start_task(task)

    return jsonify({
        "task_id": task.task_id,
        "status": task.status,
        "progress_url": f"/api/progress/{task.task_id}"
    }), 202


@compress_bp.route("/api/progress/<task_id>")
def get_progress(task_id: str):
    """SSE 进度推送"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            "error": "TASK_NOT_FOUND",
            "message": "任务不存在"
        }), 404

    def generate():
        """生成 SSE 事件流"""
        last_progress = -1

        while True:
            current_progress = task.progress
            current_status = task.status

            # 只在进度更新时发送事件
            if current_progress != last_progress or current_status in (TaskStatus.DONE, TaskStatus.ERROR):
                data = {
                    "stage": current_status,
                    "progress": current_progress,
                    "message": task.stage_message,
                }

                if current_status == TaskStatus.DONE and task.result:
                    data["result"] = task.result

                if current_status == TaskStatus.ERROR and task.error:
                    data["error"] = task.error

                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                last_progress = current_progress

                # 任务完成或失败时结束流
                if current_status in (TaskStatus.DONE, TaskStatus.ERROR):
                    break

            time.sleep(0.3)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 禁用缓冲
        }
    )


@compress_bp.route("/api/download/<task_id>")
def download_file(task_id: str):
    """下载压缩结果"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            "error": "TASK_NOT_FOUND",
            "message": "任务不存在"
        }), 404

    if task.status != TaskStatus.DONE:
        return jsonify({
            "error": "NOT_READY",
            "message": f"任务尚未完成（当前状态: {task.status}）"
        }), 400

    if not os.path.isfile(task.output_path):
        return jsonify({
            "error": "FILE_NOT_FOUND",
            "message": "输出文件不存在，可能已过期被清理"
        }), 404

    # 生成下载文件名
    original_name = task.original_filename
    if original_name.lower().endswith(".pdf"):
        download_name = original_name[:-4] + "_compressed.pdf"
    else:
        download_name = original_name + "_compressed.pdf"

    return send_file(
        task.output_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name
    )
