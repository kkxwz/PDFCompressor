"""
Ghostscript 压缩引擎 - 核心压缩逻辑

封装 Ghostscript 调用，将压缩参数字典转换为命令行执行。
支持进度回调，用于实时推送压缩进度。
"""
import os
import re
import shutil
import subprocess
import logging
from typing import Callable, Optional

import config
from compress.profiles import get_profile

logger = logging.getLogger(__name__)


def find_ghostscript() -> Optional[str]:
    """查找 Ghostscript 可执行文件路径"""
    for path in config.GS_PATHS:
        if os.path.isabs(path):
            # 绝对路径，直接检查
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        else:
            # 相对路径或命令名，使用 shutil.which 查找
            found = shutil.which(path)
            if found:
                return found
    return None


def get_gs_version(gs_path: str) -> Optional[str]:
    """获取 Ghostscript 版本"""
    try:
        result = subprocess.run(
            [gs_path, "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return None


def _validate_pdf_path(path: str) -> bool:
    """确保路径是安全的 PDF 文件路径"""
    if not os.path.isfile(path):
        return False
    if not path.lower().endswith('.pdf'):
        return False
    # 禁止路径遍历：确保解析后的路径在允许的目录内
    real_path = os.path.realpath(path)
    upload_dir = os.path.realpath(config.UPLOAD_FOLDER)
    output_dir = os.path.realpath(config.OUTPUT_FOLDER)
    return real_path.startswith(upload_dir) or real_path.startswith(output_dir)


def _build_gs_command(gs_path: str, input_path: str, output_path: str,
                      profile: dict) -> list:
    """
    构建 Ghostscript 命令行参数列表

    注意：ACS ImageDict 必须通过 -c PostScript 代码传入，不能用 -d 参数。
    """
    cmd = [gs_path]

    # 基础参数
    cmd.extend([
        "-sDEVICE=pdfwrite",
        f"-dCompatibilityLevel={profile.get('compatibility_level', '1.5')}",
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",
    ])

    # 图像降采样参数
    bool_params = [
        "DownsampleColorImages", "DownsampleGrayImages", "DownsampleMonoImages",
        "EmbedAllFonts", "SubsetFonts", "CompressFonts",
        "DetectDuplicateImages", "AutoFilterColorImages", "AutoFilterGrayImages",
        "Optimize", "PreserveHalftoneInfo", "PreserveOverprintSettings",
        "PreserveMarkedContent",
    ]

    int_params = [
        "ColorImageResolution", "GrayImageResolution", "MonoImageResolution",
    ]

    float_params = [
        "ColorImageDownsampleThreshold", "GrayImageDownsampleThreshold",
        "MonoImageDownsampleThreshold",
    ]

    str_params = [
        "ColorImageDownsampleType", "GrayImageDownsampleType",
        "MonoImageDownsampleType", "ColorConversionStrategy",
        "TransferFunctionInfo", "UCRandBGInfo",
    ]

    # 添加布尔参数
    for param in bool_params:
        if param in profile:
            value = "true" if profile[param] else "false"
            cmd.append(f"-d{param}={value}")

    # 添加整数参数
    for param in int_params:
        if param in profile:
            cmd.append(f"-d{param}={profile[param]}")

    # 添加浮点参数
    for param in float_params:
        if param in profile:
            cmd.append(f"-d{param}={profile[param]}")

    # 添加字符串参数（带 / 前缀的 PostScript 名称）
    for param in str_params:
        if param in profile:
            cmd.append(f"-d{param}={profile[param]}")

    # 构建 PostScript 代码设置 ACS ImageDict（必须通过 -c 传入）
    ps_code = "<< "

    # 彩色图像 ACS ImageDict
    if "ColorImageQFactor" in profile:
        qfactor = profile["ColorImageQFactor"]
        h_samples = profile.get("ColorHSamples", "[1 1 1 1]")
        v_samples = profile.get("ColorVSamples", "[1 1 1 1]")
        ps_code += (
            f"/ColorACSImageDict << /QFactor {qfactor} /Blend 1 "
            f"/ColorTransform 1 /HSamples {h_samples} /VSamples {v_samples} >> "
        )

    # 灰度图像 ACS ImageDict
    if "GrayImageQFactor" in profile:
        qfactor = profile["GrayImageQFactor"]
        h_samples = profile.get("GrayHSamples", "[1 1 1 1]")
        v_samples = profile.get("GrayVSamples", "[1 1 1 1]")
        ps_code += (
            f"/GrayACSImageDict << /QFactor {qfactor} /Blend 1 "
            f"/ColorTransform 1 /HSamples {h_samples} /VSamples {v_samples} >> "
        )

    ps_code += ">> setdistillerparams"

    # 输出文件（必须在 -c 和 -f 之前）
    cmd.append(f"-sOutputFile={output_path}")

    # PostScript 代码设置 ACS ImageDict
    cmd.extend(["-c", ps_code])

    # 输入文件（-f 必须在 -c 之后）
    cmd.extend(["-f", input_path])

    return cmd


def _parse_progress(line: str, total_pages: int) -> Optional[int]:
    """
    从 Ghostscript 输出中解析进度

    Ghostscript 输出格式示例：
    - "Processing pages 1 through 12."（开始处理）
    - "Page 1" / "Page 2"（处理每页）
    """
    # 尝试解析总页数
    match = re.search(r"Processing pages \d+ through (\d+)", line)
    if match:
        return 0  # 返回 0 表示已获取总页数

    # 尝试解析当前页
    match = re.search(r"Page (\d+)", line)
    if match and total_pages > 0:
        current_page = int(match.group(1))
        progress = min(int((current_page / total_pages) * 100), 99)
        return progress

    return None


def _get_total_pages(gs_path: str, input_path: str) -> int:
    """获取 PDF 总页数"""
    try:
        cmd = [
            gs_path,
            "-q", "-dNODISPLAY", "-dBATCH", "-dNOPAUSE",
            "-c",
            f"({input_path}) (r) file runpdfbegin pdfpagecount = quit"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        match = re.search(r"(\d+)", output)
        if match:
            return int(match.group(1))
    except Exception as e:
        logger.warning(f"获取 PDF 页数失败: {e}")

    return 0


def compress_pdf(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback: Optional[Callable[[int, str], None]] = None,
    timeout: int = None
) -> dict:
    """
    压缩 PDF 文件

    Args:
        input_path: 输入 PDF 文件路径
        output_path: 输出 PDF 文件路径
        level: 压缩级别 (low/medium/high)
        progress_callback: 进度回调函数 callback(progress_percent, stage_message)
        timeout: 超时时间（秒）

    Returns:
        dict: 压缩结果 {
            "success": bool,
            "original_size": int,
            "compressed_size": int,
            "ratio": float,
            "error": Optional[str]
        }
    """
    if timeout is None:
        timeout = config.COMPRESS_TIMEOUT

    # 获取压缩参数
    profile = get_profile(level)

    # 查找 Ghostscript
    gs_path = find_ghostscript()
    if not gs_path:
        return {
            "success": False,
            "error": "未找到 Ghostscript，请安装 Ghostscript 后重试"
        }

    # 检查输入文件
    if not os.path.isfile(input_path):
        return {
            "success": False,
            "error": f"输入文件不存在: {input_path}"
        }

    # 校验文件路径安全性（防止路径遍历和参数注入）
    if not _validate_pdf_path(input_path):
        return {
            "success": False,
            "error": "无效的文件路径"
        }

    # 校验输出路径安全性
    if not _validate_pdf_path(output_path):
        return {
            "success": False,
            "error": "无效的输出路径"
        }

    original_size = os.path.getsize(input_path)

    if progress_callback:
        progress_callback(5, "正在分析 PDF 文件...")

    # 获取总页数
    total_pages = _get_total_pages(gs_path, input_path)

    if progress_callback:
        progress_callback(10, "正在压缩 PDF...")

    # 构建命令
    cmd = _build_gs_command(gs_path, input_path, output_path, profile)
    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        # 执行 Ghostscript
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 实时读取输出
        current_progress = 10
        for line in process.stderr:
            line = line.strip()
            if line:
                progress = _parse_progress(line, total_pages)
                if progress is not None and progress > current_progress:
                    current_progress = progress
                    if total_pages > 0:
                        # 从 line 中提取当前页码
                        match = re.search(r"Page (\d+)", line)
                        if match:
                            page_num = match.group(1)
                            if progress_callback:
                                progress_callback(
                                    current_progress,
                                    f"正在压缩第 {page_num}/{total_pages} 页..."
                                )
                    else:
                        if progress_callback:
                            progress_callback(current_progress, "正在压缩...")

        # 等待完成
        process.wait(timeout=timeout)

        if process.returncode != 0:
            stderr_output = process.stderr.read() if process.stderr else ""
            return {
                "success": False,
                "error": f"Ghostscript 执行失败 (code={process.returncode}): {stderr_output}"
            }

    except subprocess.TimeoutExpired:
        process.kill()
        return {
            "success": False,
            "error": f"压缩超时（超过 {timeout} 秒），请尝试使用更小的文件或更低的压缩级别"
        }
    except Exception as e:
        logger.exception("压缩过程发生异常")
        return {
            "success": False,
            "error": f"压缩过程发生异常: {str(e)}"
        }

    # 检查输出文件
    if not os.path.isfile(output_path):
        return {
            "success": False,
            "error": "压缩失败：未生成输出文件"
        }

    compressed_size = os.path.getsize(output_path)

    # 如果压缩后反而变大，返回原文件
    if compressed_size >= original_size:
        # 复制原文件作为输出
        shutil.copy2(input_path, output_path)
        compressed_size = original_size
        logger.warning(f"压缩后文件变大 ({original_size} -> {compressed_size})，返回原文件")
        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "ratio": 0.0,
            "warning": "该文件已高度优化，无法进一步压缩"
        }

    ratio = (1 - compressed_size / original_size) * 100

    if progress_callback:
        progress_callback(100, "压缩完成！")

    return {
        "success": True,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": round(ratio, 1)
    }
