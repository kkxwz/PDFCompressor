# -*- mode: python ; coding: utf-8 -*-
"""
PDF Compressor - PyInstaller Build Configuration

Usage:
    pyinstaller build.spec

Or use platform-specific build scripts:
    macOS:   bash scripts/build_mac.sh
    Windows: scripts\build_windows.bat
"""
import os
import sys
import platform

block_cipher = None

# Project root directory (SPECPATH is a PyInstaller built-in variable pointing to spec file dir)
PROJECT_DIR = SPECPATH

# ========== Data Files ==========
datas = [
    (os.path.join(PROJECT_DIR, 'templates'), 'templates'),
    (os.path.join(PROJECT_DIR, 'static'), 'static'),
]

# ========== Ghostscript Binaries ==========
binaries = []

system = platform.system()
vendor_dir = os.path.join(PROJECT_DIR, 'vendor', 'ghostscript')

if system == 'Darwin':
    # macOS: find gs binary
    gs_path = os.path.join(vendor_dir, 'gs')
    if not os.path.isfile(gs_path):
        # Try to get from Homebrew
        import shutil
        gs_path = shutil.which('gs')
    if gs_path and os.path.isfile(gs_path):
        binaries.append((gs_path, 'vendor/ghostscript'))
        # Collect gs dependent dynamic libraries
        gs_dir = os.path.dirname(gs_path)
        # Find Ghostscript Resource directory
        for search_dir in [
            os.path.join(gs_dir, '..', 'share', 'ghostscript'),
            os.path.join(gs_dir, '..', 'lib', 'ghostscript'),
            '/opt/homebrew/share/ghostscript',
            '/usr/local/share/ghostscript',
        ]:
            if os.path.isdir(search_dir):
                # Find latest version Resource directory
                for item in os.listdir(search_dir):
                    resource_dir = os.path.join(search_dir, item, 'Resource')
                    if os.path.isdir(resource_dir):
                        datas.append((resource_dir,
                                      os.path.join('vendor', 'ghostscript', 'share', item, 'Resource')))
                        break
                break

elif system == 'Windows':
    # Windows: collect Ghostscript files
    machine = platform.machine().lower()

    # Prefer vendor directory
    for sub_dir in ['arm64', 'x64', '']:
        gs_dir = os.path.join(vendor_dir, sub_dir) if sub_dir else vendor_dir
        gs_exe = os.path.join(gs_dir, 'gswin64c.exe')
        if os.path.isfile(gs_exe):
            binaries.append((gs_exe,
                             os.path.join('vendor', 'ghostscript', sub_dir) if sub_dir else 'vendor/ghostscript'))
            # Collect DLL files
            for f in os.listdir(gs_dir):
                if f.endswith('.dll'):
                    binaries.append((os.path.join(gs_dir, f),
                                     os.path.join('vendor', 'ghostscript', sub_dir) if sub_dir else 'vendor/ghostscript'))
            # Collect lib directory (Ghostscript resource files)
            lib_dir = os.path.join(gs_dir, 'lib')
            if os.path.isdir(lib_dir):
                datas.append((lib_dir,
                              os.path.join('vendor', 'ghostscript', sub_dir, 'lib') if sub_dir
                              else os.path.join('vendor', 'ghostscript', 'lib')))
            break

# ========== Build Configuration ==========
a = Analysis(
    [os.path.join(PROJECT_DIR, 'app.py')],
    pathex=[PROJECT_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'flask',
        'werkzeug',
        'engineio.async_drivers.threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas',
        'IPython', 'jupyter', 'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ========== Executable ==========
exe_options = dict(
    pyz=pyz,
    scripts=a.scripts,
    strip=False,
    upx=True,
    console=True,         # Keep console window for log output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if system == 'Darwin':
    # macOS: generate .app bundle
    exe_options['name'] = 'PDFCompressor'
    exe_options['exclude_binaries'] = True  # macOS COLLECT requires this
    exe = EXE(**exe_options)
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='PDFCompressor',
    )
    app = BUNDLE(
        coll,
        name='PDF Compressor.app',
        icon=None,  # Can set .icns icon file path here
        bundle_identifier='com.tools.pdfcompressor',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1',
            'NSHumanReadableCopyright': 'PDF Compressor',
            'CFBundleDisplayName': 'PDF Compressor',
        },
    )

else:
    # Windows/Linux: generate single-file exe
    exe_options['name'] = 'PDFCompressor'
    exe_options['icon'] = None  # Can set .ico icon file path here
    exe_options['binaries'] = a.binaries
    exe_options['zipfiles'] = a.zipfiles
    exe_options['datas'] = a.datas
    exe_options['exclude_binaries'] = False
    exe = EXE(**exe_options)
