"""
PDF 压缩工具 - 全局配置

支持开发环境和 PyInstaller 打包环境。
"""
import os
import sys
import platform

# ========== 路径检测 ==========

def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_app_dir() -> str:
    """获取应用数据目录（用于存放上传/输出文件，必须可写）"""
    if is_frozen():
        system = platform.system()
        if system == "Windows":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            app_dir = os.path.join(base, "PDFCompressor")
        elif system == "Darwin":
            app_dir = os.path.join(os.path.expanduser("~"), "Library",
                                   "Application Support", "PDFCompressor")
        else:
            app_dir = os.path.join(os.path.expanduser("~"), ".pdf-compressor")
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    return app_dir


def get_resource_dir() -> str:
    """获取资源目录（模板/静态文件/Ghostscript，只读）"""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


# ========== 基础路径 ==========

APP_DIR = get_app_dir()
RESOURCE_DIR = get_resource_dir()

# 服务器配置
HOST = "127.0.0.1"
PORT = 5000
DEBUG = not is_frozen()  # 打包后关闭调试模式

# 上传配置
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {"pdf"}
UPLOAD_FOLDER = os.path.join(APP_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(APP_DIR, "outputs")

# 文件自动清理时间（秒）
FILE_CLEANUP_SECONDS = 10 * 60  # 10 分钟

# 压缩超时（秒）
COMPRESS_TIMEOUT = 5 * 60  # 5 分钟

# ========== Ghostscript 路径 ==========

def _build_gs_paths() -> list:
    """构建 Ghostscript 搜索路径列表"""
    paths = []

    if is_frozen():
        # 打包模式：优先查找内嵌的 Ghostscript
        vendor_dir = os.path.join(RESOURCE_DIR, "vendor", "ghostscript")
        system = platform.system()

        if system == "Darwin":
            # macOS: Universal Binary
            paths.append(os.path.join(vendor_dir, "gs"))
        elif system == "Windows":
            # Windows: 根据架构选择
            machine = platform.machine().lower()
            if machine in ("arm64", "aarch64"):
                paths.append(os.path.join(vendor_dir, "arm64", "gswin64c.exe"))
            paths.append(os.path.join(vendor_dir, "x64", "gswin64c.exe"))
            paths.append(os.path.join(vendor_dir, "gswin64c.exe"))

    # 开发模式或 fallback：vendor 目录 + 系统 PATH
    paths.extend([
        os.path.join(RESOURCE_DIR, "vendor", "ghostscript", "mac", "gs"),
        os.path.join(RESOURCE_DIR, "vendor", "ghostscript", "windows", "gswin64c.exe"),
        "gs",           # macOS/Linux 系统 PATH
        "gswin64c",     # Windows 系统 PATH
        "gswin32c",     # Windows 32-bit
    ])

    return paths


GS_PATHS = _build_gs_paths()

# ========== 确保目录存在 ==========

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
