"""
Ghostscript Compression Engine - Core compression logic

Wraps Ghostscript calls, converting compression parameter dicts to CLI commands.
Supports progress callbacks for real-time compression progress.
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
    """Find Ghostscript executable path"""
    for path in config.GS_PATHS:
        if os.path.isabs(path):
            # Absolute path, check directly
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        else:
            # Relative path or command name, use shutil.which
            found = shutil.which(path)
            if found:
                return found
    return None


def get_gs_version(gs_path: str) -> Optional[str]:
    """Get Ghostscript version"""
    try:
        result = subprocess.run(
            [gs_path, "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return None


def _validate_pdf_path(path: str) -> bool:
    """Ensure path is a safe PDF file path"""
    if not os.path.isfile(path):
        return False
    if not path.lower().endswith('.pdf'):
        return False
    # Prevent path traversal: ensure resolved path is within allowed directories
    real_path = os.path.realpath(path)
    upload_dir = os.path.realpath(config.UPLOAD_FOLDER)
    output_dir = os.path.realpath(config.OUTPUT_FOLDER)
    return real_path.startswith(upload_dir) or real_path.startswith(output_dir)


def _build_gs_command(gs_path: str, input_path: str, output_path: str,
                      profile: dict) -> list:
    """
    Build Ghostscript CLI argument list

    Note: ACS ImageDict must be passed via -c PostScript code, not -d params.
    """
    cmd = [gs_path]

    # Base params
    cmd.extend([
        "-sDEVICE=pdfwrite",
        f"-dCompatibilityLevel={profile.get('compatibility_level', '1.5')}",
        "-dNOPAUSE",
        "-dBATCH",
        "-dSAFER",
    ])

    # Image downsampling params
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

    # Add boolean params
    for param in bool_params:
        if param in profile:
            value = "true" if profile[param] else "false"
            cmd.append(f"-d{param}={value}")

    # Add integer params
    for param in int_params:
        if param in profile:
            cmd.append(f"-d{param}={profile[param]}")

    # Add float params
    for param in float_params:
        if param in profile:
            cmd.append(f"-d{param}={profile[param]}")

    # Add string params (PostScript names with / prefix)
    for param in str_params:
        if param in profile:
            cmd.append(f"-d{param}={profile[param]}")

    # Build PostScript code for ACS ImageDict (must pass via -c)
    ps_code = "<< "

    # Color image ACS ImageDict
    if "ColorImageQFactor" in profile:
        qfactor = profile["ColorImageQFactor"]
        h_samples = profile.get("ColorHSamples", "[1 1 1 1]")
        v_samples = profile.get("ColorVSamples", "[1 1 1 1]")
        ps_code += (
            f"/ColorACSImageDict << /QFactor {qfactor} /Blend 1 "
            f"/ColorTransform 1 /HSamples {h_samples} /VSamples {v_samples} >> "
        )

    # Grayscale image ACS ImageDict
    if "GrayImageQFactor" in profile:
        qfactor = profile["GrayImageQFactor"]
        h_samples = profile.get("GrayHSamples", "[1 1 1 1]")
        v_samples = profile.get("GrayVSamples", "[1 1 1 1]")
        ps_code += (
            f"/GrayACSImageDict << /QFactor {qfactor} /Blend 1 "
            f"/ColorTransform 1 /HSamples {h_samples} /VSamples {v_samples} >> "
        )

    ps_code += ">> setdistillerparams"

    # Output file (must be before -c and -f)
    cmd.append(f"-sOutputFile={output_path}")

    # PostScript code for ACS ImageDict
    cmd.extend(["-c", ps_code])

    # Input file (-f must come after -c)
    cmd.extend(["-f", input_path])

    return cmd


def _parse_progress(line: str, total_pages: int) -> Optional[int]:
    """
    Parse progress from Ghostscript output

    Ghostscript output format examples:
    - "Processing pages 1 through 12." (start processing)
    - "Page 1" / "Page 2" (per page)
    """
    # Try to parse total pages
    match = re.search(r"Processing pages \d+ through (\d+)", line)
    if match:
        return 0  # Return 0 means total pages acquired

    # Try to parse current page
    match = re.search(r"Page (\d+)", line)
    if match and total_pages > 0:
        current_page = int(match.group(1))
        progress = min(int((current_page / total_pages) * 100), 99)
        return progress

    return None


def _get_total_pages(gs_path: str, input_path: str) -> int:
    """Get total PDF page count"""
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
        logger.warning(f"Failed to get PDF page count: {e}")

    return 0


def compress_pdf(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback: Optional[Callable[[int, str], None]] = None,
    timeout: int = None
) -> dict:
    """
    Compress PDF file

    Args:
        input_path: Input PDF file path
        output_path: Output PDF file path
        level: Compression level (low/medium/high)
        progress_callback: Progress callback function callback(progress_percent, stage_message)
        timeout: Timeout in seconds

    Returns:
        dict: Compression result {
            "success": bool,
            "original_size": int,
            "compressed_size": int,
            "ratio": float,
            "error": Optional[str]
        }
    """
    if timeout is None:
        timeout = config.COMPRESS_TIMEOUT

    # Get compression profile
    profile = get_profile(level)

    # Find Ghostscript
    gs_path = find_ghostscript()
    if not gs_path:
        return {
            "success": False,
            "error": "Ghostscript not found. Please install Ghostscript and try again."
        }

    # Check input file
    if not os.path.isfile(input_path):
        return {
            "success": False,
            "error": f"Input file not found: {input_path}"
        }

    # Validate file path security (prevent path traversal and parameter injection)
    if not _validate_pdf_path(input_path):
        return {
            "success": False,
            "error": "Invalid file path"
        }

    # Validate output path security
    if not _validate_pdf_path(output_path):
        return {
            "success": False,
            "error": "Invalid output path"
        }

    original_size = os.path.getsize(input_path)

    if progress_callback:
        progress_callback(5, "Analyzing PDF file...")

    # Get total pages
    total_pages = _get_total_pages(gs_path, input_path)

    if progress_callback:
        progress_callback(10, "Compressing PDF...")

    # Build command
    cmd = _build_gs_command(gs_path, input_path, output_path, profile)
    logger.info(f"Executing command: {' '.join(cmd)}")

    try:
        # Execute Ghostscript
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Read output in real-time
        current_progress = 10
        for line in process.stderr:
            line = line.strip()
            if line:
                progress = _parse_progress(line, total_pages)
                if progress is not None and progress > current_progress:
                    current_progress = progress
                    if total_pages > 0:
                        # Extract current page from line
                        match = re.search(r"Page (\d+)", line)
                        if match:
                            page_num = match.group(1)
                            if progress_callback:
                                progress_callback(
                                    current_progress,
                                    f"Compressing page {page_num}/{total_pages}..."
                                )
                    else:
                        if progress_callback:
                            progress_callback(current_progress, "Compressing...")

        # Wait for completion
        process.wait(timeout=timeout)

        if process.returncode != 0:
            stderr_output = process.stderr.read() if process.stderr else ""
            return {
                "success": False,
                "error": f"Ghostscript failed (code={process.returncode}): {stderr_output}"
            }

    except subprocess.TimeoutExpired:
        process.kill()
        return {
            "success": False,
            "error": f"Compression timed out (exceeded {timeout}s). Try a smaller file or lower compression level."
        }
    except Exception as e:
        logger.exception("Compression error")
        return {
            "success": False,
            "error": f"Compression error: {str(e)}"
        }

    # Check output file
    if not os.path.isfile(output_path):
        return {
            "success": False,
            "error": "Compression failed: no output file generated"
        }

    compressed_size = os.path.getsize(output_path)

    # If compressed file is larger, return original
    if compressed_size >= original_size:
        # Copy original as output
        shutil.copy2(input_path, output_path)
        compressed_size = original_size
        logger.warning(f"Compressed file larger ({original_size} -> {compressed_size}), returning original")
        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "ratio": 0.0,
            "warning": "File already highly optimized, cannot compress further"
        }

    ratio = (1 - compressed_size / original_size) * 100

    if progress_callback:
        progress_callback(100, "Compression complete!")

    return {
        "success": True,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": round(ratio, 1)
    }
