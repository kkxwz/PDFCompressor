@echo off
REM ============================================
REM PDF Compressor - Windows Build Script
REM ============================================
setlocal enabledelayedexpansion

echo ============================================
echo   PDF Compressor Windows Build
echo ============================================

REM Get project root directory
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
cd /d "%PROJECT_DIR%"

REM 1. Check dependencies
echo [1/5] Checking dependencies...
python --version 2>nul
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.10+
    exit /b 1
)
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM 2. Check Ghostscript
echo [2/5] Checking Ghostscript...
set "VENDOR_GS=%PROJECT_DIR%\vendor\ghostscript"

REM Detect architecture
echo %PROCESSOR_ARCHITECTURE% | findstr /i "ARM64" >nul
if not errorlevel 1 (
    set "ARCH=arm64"
    set "GS_EXE=gswin64c.exe"
) else (
    set "ARCH=x64"
    set "GS_EXE=gswin64c.exe"
)

REM Search common Ghostscript locations
set "GS_FOUND="
for %%P in (
    "%VENDOR_GS%\%ARCH%\%GS_EXE%"
    "%VENDOR_GS%\%GS_EXE%"
    "C:\Program Files\gs\gs*\bin\%GS_EXE%"
    "C:\Program Files (x86)\gs\gs*\bin\%GS_EXE%"
) do (
    if exist %%P (
        set "GS_FOUND=%%~fP"
        goto :gs_found
    )
)

REM Try PATH
where %GS_EXE% >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where %GS_EXE%') do (
        set "GS_FOUND=%%I"
        goto :gs_found
    )
)

echo Error: Ghostscript not found
echo Please download from https://ghostscript.com/releases/gsdnld.html
echo and install.
exit /b 1

:gs_found
echo Ghostscript: %GS_FOUND%

REM 3. Prepare vendor directory
echo [3/5] Preparing Ghostscript files...
set "GS_BIN_DIR=%~dp0"
for %%I in ("%GS_FOUND%") do set "GS_BIN_DIR=%%~dpI"

set "DEST_DIR=%VENDOR_GS%\%ARCH%"
if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

REM Copy gs executable
copy /Y "%GS_FOUND%" "%DEST_DIR%\" >nul

REM Copy DLL files
for %%F in ("%GS_BIN_DIR%*.dll") do (
    copy /Y "%%F" "%DEST_DIR%\" >nul
)

REM Copy lib directory
if exist "%GS_BIN_DIR%..\lib" (
    xcopy /Y /E /I "%GS_BIN_DIR%..\lib" "%DEST_DIR%\lib" >nul
)
echo   Copied Ghostscript to vendor\ghostscript\%ARCH%

REM 4. Install Python dependencies
echo [4/5] Installing Python dependencies...
pip install -r requirements.txt -q

REM 5. Build
echo [5/5] Starting PyInstaller build...
pyinstaller build.spec --clean --noconfirm

echo.
echo ============================================
echo   Build complete!
echo ============================================
if exist "dist\PDFCompressor.exe" (
    for %%F in ("dist\PDFCompressor.exe") do echo   Artifact: dist\PDFCompressor.exe (%%~zF bytes^)
    echo.
    echo   Test run: dist\PDFCompressor.exe
    echo   Distribute: Send PDFCompressor.exe directly to users
) else (
    echo   Artifacts in dist\ directory
)
endlocal
