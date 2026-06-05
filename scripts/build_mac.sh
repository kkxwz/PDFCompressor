#!/bin/bash
# ============================================
# PDF Compressor - macOS 构建脚本
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================"
echo "  PDF Compressor macOS 构建"
echo "============================================"

# 1. 检查依赖
echo "[1/5] 检查依赖..."
python3 --version
pip3 show pyinstaller >/dev/null 2>&1 || pip3 install pyinstaller

# 检查 Ghostscript
GS_PATH=$(which gs 2>/dev/null || echo "")
if [ -z "$GS_PATH" ]; then
    echo "错误: 未找到 Ghostscript，请先安装: brew install ghostscript"
    exit 1
fi
echo "Ghostscript: $GS_PATH ($($GS_PATH --version))"

# 2. 准备 vendor 目录
echo "[2/5] 准备 Ghostscript 二进制..."
VENDOR_GS="$PROJECT_DIR/vendor/ghostscript"
mkdir -p "$VENDOR_GS"

# 复制 gs 二进制
cp "$GS_PATH" "$VENDOR_GS/gs"
chmod +x "$VENDOR_GS/gs"

# 如果是 Homebrew 安装的，尝试创建 Universal Binary
BREW_PREFIX=$(brew --prefix 2>/dev/null || echo "")
if [ -n "$BREW_PREFIX" ]; then
    GS_ARM="$BREW_PREFIX/bin/gs"
    # 检查是否有不同架构的版本
    if file "$GS_ARM" | grep -q "arm64"; then
        echo "  检测到 ARM64 版本"
    fi
fi
echo "  已复制 Ghostscript 到 vendor 目录"

# 3. 安装 Python 依赖
echo "[3/5] 安装 Python 依赖..."
pip3 install -r requirements.txt -q

# 4. 构建
echo "[4/5] 开始 PyInstaller 构建..."
pyinstaller build.spec --clean --noconfirm

# 5. 结果
echo "[5/5] 构建完成！"
echo ""
if [ -d "dist/PDF Compressor.app" ]; then
    APP_SIZE=$(du -sh "dist/PDF Compressor.app" | cut -f1)
    echo "  产物: dist/PDF Compressor.app ($APP_SIZE)"
    echo ""
    echo "  测试运行:"
    echo "    open \"dist/PDF Compressor.app\""
    echo ""
    echo "  分发方式:"
    echo "    1. 压缩为 DMG: hdiutil create -volname 'PDF Compressor' -srcfolder 'dist/PDF Compressor.app' -ov dist/PDFCompressor.dmg"
    echo "    2. 直接复制 .app 到其他 Mac"
else
    echo "  产物在 dist/ 目录下"
fi
