"""
Compression Task Routes - Start compression, progress push, download result
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
    """Find uploaded file by file_id, return (file_path, original_filename)"""
    pattern = os.path.join(config.UPLOAD_FOLDER, f"{file_id}_*.pdf")
    matches = glob.glob(pattern)
    if not matches:
        return None, None

    file_path = matches[0]
    # Extract original filename (strip file_id_ prefix)
    basename = os.path.basename(file_path)
    original_filename = basename[len(file_id) + 1:]  # +1 for underscore
    return file_path, original_filename


@compress_bp.route("/api/compress", methods=["POST"])
def start_compress():
    """Start compression task"""
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "INVALID_REQUEST",
            "message": "Invalid request data"
        }), 400

    file_id = data.get("file_id")
    level = data.get("level", "medium")

    if not file_id:
        return jsonify({
            "error": "MISSING_FILE_ID",
            "message": "Missing file_id"
        }), 400

    if level not in ("low", "medium", "high"):
        return jsonify({
            "error": "INVALID_LEVEL",
            "message": "Invalid compression level, available: low, medium, high"
        }), 400

    # Find uploaded file
    input_path, original_filename = _find_upload_file(file_id)
    if not input_path:
        return jsonify({
            "error": "FILE_NOT_FOUND",
            "message": "Uploaded file not found, please re-upload"
        }), 404

    # Create and start task
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
    """SSE progress push"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            "error": "TASK_NOT_FOUND",
            "message": "Task not found"
        }), 404

    def generate():
        """Generate SSE event stream"""
        last_progress = -1

        while True:
            current_progress = task.progress
            current_status = task.status

            # Only send event when progress updates
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

                # End stream when task completes or fails
                if current_status in (TaskStatus.DONE, TaskStatus.ERROR):
                    break

            time.sleep(0.3)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx disable buffering
        }
    )


@compress_bp.route("/api/download/<task_id>")
def download_file(task_id: str):
    """Download compression result"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            "error": "TASK_NOT_FOUND",
            "message": "Task not found"
        }), 404

    if task.status != TaskStatus.DONE:
        return jsonify({
            "error": "NOT_READY",
            "message": f"Task not yet complete (current status: {task.status})"
        }), 400

    if not os.path.isfile(task.output_path):
        return jsonify({
            "error": "FILE_NOT_FOUND",
            "message": "Output file not found, may have been cleaned up"
        }), 404

    # Generate download filename
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
