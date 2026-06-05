"""
PDF 压缩工具 - Flask 主应用

启动方式：
    python app.py

访问：http://127.0.0.1:5000
"""
import os
import sys
import logging
import webbrowser
import threading
import atexit

from flask import Flask, render_template

import config
from routes.upload import upload_bp
from routes.compress import compress_bp
from routes.health import health_bp

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """创建 Flask 应用"""
    resource_dir = config.RESOURCE_DIR
    template_folder = os.path.join(resource_dir, "templates")
    static_folder = os.path.join(resource_dir, "static")

    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=static_folder
    )

    # 配置文件大小限制
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    # 注册蓝图
    app.register_blueprint(upload_bp)
    app.register_blueprint(compress_bp)
    app.register_blueprint(health_bp)

    # 主页路由
    @app.route("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()


def open_browser():
    """自动打开浏览器"""
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")


def cleanup_temp_files():
    """退出时清理临时文件"""
    import shutil
    for folder in [config.UPLOAD_FOLDER, config.OUTPUT_FOLDER]:
        if os.path.isdir(folder):
            try:
                for f in os.listdir(folder):
                    filepath = os.path.join(folder, f)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
            except Exception:
                pass


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("PDF Compressor 启动中...")
    logger.info(f"访问地址: http://{config.HOST}:{config.PORT}")
    logger.info(f"应用数据: {config.APP_DIR}")
    logger.info(f"资源目录: {config.RESOURCE_DIR}")
    logger.info(f"打包模式: {'是' if config.is_frozen() else '否'}")
    logger.info("=" * 50)

    # 检查 Ghostscript
    from compress.engine import find_ghostscript, get_gs_version
    gs_path = find_ghostscript()
    if gs_path:
        gs_version = get_gs_version(gs_path)
        logger.info(f"Ghostscript: {gs_path} (v{gs_version})")
    else:
        logger.warning("Ghostscript 未找到！压缩功能不可用。")

    # 注册退出清理
    atexit.register(cleanup_temp_files)

    # 延迟打开浏览器（打包模式和正式模式都自动打开）
    if not config.DEBUG:
        threading.Timer(1.5, open_browser).start()
        print(f"\n{'=' * 50}")
        print(f"  PDF Compressor 已启动")
        print(f"  浏览器将自动打开，如未打开请访问:")
        print(f"  http://{config.HOST}:{config.PORT}")
        print(f"  按 Ctrl+C 退出")
        print(f"{'=' * 50}\n")

    # 启动服务
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True
    )
