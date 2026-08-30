#!/bin/bash
# ============================================
# SlimPDF - macOS Build Script
# ============================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "============================================"
echo "  SlimPDF macOS Build"
echo "============================================"

# 1. Check dependencies
echo "[1/5] Checking dependencies..."
python3 --version

# Require Python >= 3.10 (project uses builtin generics / X|Y annotations)
PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=${PY_VER%%.*}
PY_MINOR=${PY_VER#*.}
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "Error: Python >= 3.10 required (found $PY_VER)."
    exit 1
fi

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

# Copy Resource files (fonts etc.) when present next to the Homebrew install,
# matching what CI does - otherwise the bundled gs may fail on font lookups
GS_SHARE="$(dirname "$(dirname "$GS_PATH")")/share/ghostscript"
if [ -d "$GS_SHARE" ]; then
    GS_VER=$(ls "$GS_SHARE" | head -1)
    if [ -d "$GS_SHARE/$GS_VER/Resource" ]; then
        mkdir -p "$VENDOR_GS/share/$GS_VER"
        cp -R "$GS_SHARE/$GS_VER/Resource" "$VENDOR_GS/share/$GS_VER/"
        echo "  Copied Ghostscript Resource ($GS_VER)"
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
if [ -d "dist/SlimPDF.app" ]; then
    APP_SIZE=$(du -sh "dist/SlimPDF.app" | cut -f1)
    echo "  Artifact: dist/SlimPDF.app ($APP_SIZE)"
    echo ""
    echo "  Test run:"
    echo "    open \"dist/SlimPDF.app\""
    echo ""
    echo "  Distribution:"
    echo "    1. Create DMG: hdiutil create -volname 'SlimPDF' -srcfolder 'dist/SlimPDF.app' -ov dist/SlimPDF.dmg"
    echo "    2. Copy .app directly to other Macs"
else
    echo "  Artifacts in dist/ directory"
fi
