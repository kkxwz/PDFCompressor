"""
Ghostscript Compression Engine - Core compression logic

Wraps Ghostscript calls, converting compression parameter dicts to CLI commands.
Supports progress callbacks for real-time compression progress.
"""
import os
import re
import shutil
import subprocess
import threading
import logging
from collections import deque
from typing import Any, Callable, Optional

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
            # errors="replace": gs may print in the platform locale encoding
            # (e.g. cp936/cp1252 on Windows); never crash on undecodable bytes
            capture_output=True, text=True, errors="replace", timeout=10
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
    # (append os.sep so sibling dirs like "uploads_evil" cannot pass the check)
    real_path = os.path.realpath(path)
    for allowed in (config.UPLOAD_FOLDER, config.OUTPUT_FOLDER):
        allowed_dir = os.path.realpath(allowed)
        if real_path.startswith(allowed_dir + os.sep):
            return True
    return False


def _validate_output_path(path: str) -> bool:
    """Ensure output path is a .pdf inside the outputs directory
    (unlike _validate_pdf_path, the file does not need to exist yet)"""
    if not path.lower().endswith('.pdf'):
        return False
    real_dir = os.path.realpath(os.path.dirname(path))
    return real_dir == os.path.realpath(config.OUTPUT_FOLDER)


def _build_gs_command(gs_path: str, input_path: str, output_path: str,
                      profile: dict[str, Any]) -> list[str]:
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
        # Escape PostScript string delimiters in path (defense in depth;
        # server-generated names normally contain no parentheses/backslashes)
        ps_path = input_path.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        cmd = [
            gs_path,
            "-q", "-dNODISPLAY", "-dBATCH", "-dNOPAUSE",
            # Explicit even though gs >= 9.50 defaults to SAFER, so older
            # Ghostscript builds stay sandboxed as well
            "-dSAFER",
            # gs >= 9.50 runs SAFER by default; grant read access to the
            # input file only, otherwise the PostScript file operator fails
            # with /invalidfileaccess and page count silently becomes 0
            f"--permit-file-read={input_path}",
            "-c",
            f"({ps_path}) (r) file runpdfbegin pdfpagecount = quit"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=30
        )
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
    progress_callback: Optional[Callable[[int, str, Optional[dict[str, Any]]], None]] = None,
    timeout: Optional[int] = None
) -> dict[str, Any]:
    """
    Compress PDF file

    Args:
        input_path: Input PDF file path
        output_path: Output PDF file path
        level: Compression level (low/medium/high)
        progress_callback: Progress callback callback(progress_percent, stage_message, meta).
            meta is a machine-readable dict ({"key": ...} plus extras for the
            "page" key) so clients can localize without parsing the English text.
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

    # Validate output path security (output file does not exist yet)
    if not _validate_output_path(output_path):
        return {
            "success": False,
            "error": "Invalid output path"
        }

    original_size = os.path.getsize(input_path)

    if progress_callback:
        progress_callback(5, "Analyzing PDF file...", {"key": "analyzing"})

    # Get total pages
    total_pages = _get_total_pages(gs_path, input_path)

    if progress_callback:
        progress_callback(10, "Compressing PDF...", {"key": "processing"})

    # Build command
    cmd = _build_gs_command(gs_path, input_path, output_path, profile)
    logger.info(f"Executing command: {' '.join(cmd)}")

    try:
        # Execute Ghostscript. Progress lines ("Page N") are printed on stdout,
        # so merge stderr into stdout and read a single pipe.
        # errors="replace": gs error text may use the platform locale encoding
        # (Windows), decoding must never raise mid-compression.
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )

        # Keep the tail of output for error reporting
        output_tail: deque[str] = deque(maxlen=50)

        def _drain_output() -> None:
            """Drain output in a background thread (prevents pipe-buffer deadlock
            and keeps process.wait(timeout=...) effective)"""
            current_progress = 10
            assert process.stdout is not None  # PIPE was requested above
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                output_tail.append(line)
                progress = _parse_progress(line, total_pages)
                if progress is not None and progress > current_progress:
                    current_progress = progress
                    if total_pages > 0:
                        # Extract current page from line
                        match = re.search(r"Page (\d+)", line)
                        if match and progress_callback:
                            progress_callback(
                                current_progress,
                                f"Compressing page {match.group(1)}/{total_pages}...",
                                {"key": "page", "current": int(match.group(1)),
                                 "total": total_pages},
                            )
                    elif progress_callback:
                        progress_callback(current_progress, "Compressing...",
                                          {"key": "processing"})

        reader = threading.Thread(target=_drain_output, daemon=True)
        reader.start()

        # Wait for completion (real timeout: the reader thread keeps the pipe drained)
        process.wait(timeout=timeout)
        reader.join(timeout=5)

        if process.returncode != 0:
            stderr_output = "\n".join(output_tail)
            return {
                "success": False,
                "error": f"Ghostscript failed (code={process.returncode}): {stderr_output}"
            }

    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
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
        if progress_callback:
            progress_callback(100, "Compression complete!", {"key": "complete"})
        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "ratio": 0.0,
            "warning": "File already highly optimized, cannot compress further"
        }

    ratio = (1 - compressed_size / original_size) * 100

    if progress_callback:
        progress_callback(100, "Compression complete!", {"key": "complete"})

    return {
        "success": True,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": round(ratio, 1)
    }
