@echo off
REM ============================================
REM PDF Compressor - Windows 构建脚本
REM ============================================
setlocal enabledelayedexpansion

echo ============================================
echo   PDF Compressor Windows 构建
echo ============================================

REM 获取项目根目录
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
cd /d "%PROJECT_DIR%"

REM 1. 检查依赖
echo [1/5] 检查依赖...
python --version 2>nul
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.10+
    exit /b 1
)
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install pyinstaller
)

REM 2. 检查 Ghostscript
echo [2/5] 检查 Ghostscript...
set "VENDOR_GS=%PROJECT_DIR%\vendor\ghostscript"

REM 检测架构
echo %PROCESSOR_ARCHITECTURE% | findstr /i "ARM64" >nul
if not errorlevel 1 (
    set "ARCH=arm64"
    set "GS_EXE=gswin64c.exe"
) else (
    set "ARCH=x64"
    set "GS_EXE=gswin64c.exe"
)

REM 在常见位置查找 Ghostscript
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

REM 尝试 PATH
where %GS_EXE% >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('where %GS_EXE%') do (
        set "GS_FOUND=%%I"
        goto :gs_found
    )
)

echo 错误: 未找到 Ghostscript
echo 请从 https://ghostscript.com/releases/gsdnld.html 下载安装
exit /b 1

:gs_found
echo Ghostscript: %GS_FOUND%

REM 3. 准备 vendor 目录
echo [3/5] 准备 Ghostscript 文件...
set "GS_BIN_DIR=%~dp0"
for %%I in ("%GS_FOUND%") do set "GS_BIN_DIR=%%~dpI"

set "DEST_DIR=%VENDOR_GS%\%ARCH%"
if not exist "%DEST_DIR%" mkdir "%DEST_DIR%"

REM 复制 gs 可执行文件
copy /Y "%GS_FOUND%" "%DEST_DIR%\" >nul

REM 复制 DLL 文件
for %%F in ("%GS_BIN_DIR%*.dll") do (
    copy /Y "%%F" "%DEST_DIR%\" >nul
)

REM 复制 lib 目录
if exist "%GS_BIN_DIR%..\lib" (
    xcopy /Y /E /I "%GS_BIN_DIR%..\lib" "%DEST_DIR%\lib" >nul
)
echo   已复制 Ghostscript 到 vendor\ghostscript\%ARCH%

REM 4. 安装 Python 依赖
echo [4/5] 安装 Python 依赖...
pip install -r requirements.txt -q

REM 5. 构建
echo [5/5] 开始 PyInstaller 构建...
pyinstaller build.spec --clean --noconfirm

echo.
echo ============================================
echo   构建完成！
echo ============================================
if exist "dist\PDFCompressor.exe" (
    for %%F in ("dist\PDFCompressor.exe") do echo   产物: dist\PDFCompressor.exe (%%~zF bytes^)
    echo.
    echo   测试运行: dist\PDFCompressor.exe
    echo   分发: 直接将 PDFCompressor.exe 发给用户即可
) else (
    echo   产物在 dist\ 目录下
)
endlocal
