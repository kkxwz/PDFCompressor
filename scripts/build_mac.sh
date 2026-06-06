#!/bin/bash
# ============================================
# PDF Compressor - macOS Build Script
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================"
echo "  PDF Compressor macOS Build"
echo "============================================"

# 1. Check dependencies
echo "[1/5] Checking dependencies..."
python3 --version
pip3 show pyinstaller >/dev/null 2>&1 || pip3 install pyinstaller

# Check Ghostscript
GS_PATH=$(which gs 2>/dev/null || echo "")
if [ -z "$GS_PATH" ]; then
    echo "Error: Ghostscript not found. Please install: brew install ghostscript"
    exit 1
fi
echo "Ghostscript: $GS_PATH ($($GS_PATH --version))"

# 2. Prepare vendor directory
echo "[2/5] Preparing Ghostscript binary..."
VENDOR_GS="$PROJECT_DIR/vendor/ghostscript"
mkdir -p "$VENDOR_GS"

# Copy gs binary
cp "$GS_PATH" "$VENDOR_GS/gs"
chmod +x "$VENDOR_GS/gs"

# If installed via Homebrew, try to create Universal Binary
BREW_PREFIX=$(brew --prefix 2>/dev/null || echo "")
if [ -n "$BREW_PREFIX" ]; then
    GS_ARM="$BREW_PREFIX/bin/gs"
    # Check for different architecture versions
    if file "$GS_ARM" | grep -q "arm64"; then
        echo "  Detected ARM64 version"
    fi
fi
echo "  Copied Ghostscript to vendor directory"

# 3. Install Python dependencies
echo "[3/5] Installing Python dependencies..."
pip3 install -r requirements.txt -q

# 4. Build
echo "[4/5] Starting PyInstaller build..."
pyinstaller build.spec --clean --noconfirm

# 5. Results
echo "[5/5] Build complete!"
echo ""
if [ -d "dist/PDF Compressor.app" ]; then
    APP_SIZE=$(du -sh "dist/PDF Compressor.app" | cut -f1)
    echo "  Artifact: dist/PDF Compressor.app ($APP_SIZE)"
    echo ""
    echo "  Test run:"
    echo "    open \"dist/PDF Compressor.app\""
    echo ""
    echo "  Distribution:"
    echo "    1. Create DMG: hdiutil create -volname 'PDF Compressor' -srcfolder 'dist/PDF Compressor.app' -ov dist/PDFCompressor.dmg"
    echo "    2. Copy .app directly to other Macs"
else
    echo "  Artifacts in dist/ directory"
fi
