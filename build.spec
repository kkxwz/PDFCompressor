# -*- mode: python ; coding: utf-8 -*-
"""
PDF Compressor - PyInstaller 打包配置

用法：
    pyinstaller build.spec

或分平台使用构建脚本：
    macOS:   bash scripts/build_mac.sh
    Windows: scripts\build_windows.bat
"""
import os
import sys
import platform

block_cipher = None

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== 数据文件 ==========
datas = [
    (os.path.join(PROJECT_DIR, 'templates'), 'templates'),
    (os.path.join(PROJECT_DIR, 'static'), 'static'),
]

# ========== Ghostscript 二进制 ==========
binaries = []

system = platform.system()
vendor_dir = os.path.join(PROJECT_DIR, 'vendor', 'ghostscript')

if system == 'Darwin':
    # macOS: 查找 gs 二进制
    gs_path = os.path.join(vendor_dir, 'gs')
    if not os.path.isfile(gs_path):
        # 尝试从 Homebrew 获取
        import shutil
        gs_path = shutil.which('gs')
    if gs_path and os.path.isfile(gs_path):
        binaries.append((gs_path, 'vendor/ghostscript'))
        # 收集 gs 依赖的动态库
        gs_dir = os.path.dirname(gs_path)
        # 查找 Ghostscript 的 Resource 目录
        for search_dir in [
            os.path.join(gs_dir, '..', 'share', 'ghostscript'),
            os.path.join(gs_dir, '..', 'lib', 'ghostscript'),
            '/opt/homebrew/share/ghostscript',
            '/usr/local/share/ghostscript',
        ]:
            if os.path.isdir(search_dir):
                # 查找最新版本的 Resource 目录
                for item in os.listdir(search_dir):
                    resource_dir = os.path.join(search_dir, item, 'Resource')
                    if os.path.isdir(resource_dir):
                        datas.append((resource_dir,
                                      os.path.join('vendor', 'ghostscript', 'share', item, 'Resource')))
                        break
                break

elif system == 'Windows':
    # Windows: 收集 Ghostscript 文件
    machine = platform.machine().lower()

    # 优先使用 vendor 目录
    for sub_dir in ['arm64', 'x64', '']:
        gs_dir = os.path.join(vendor_dir, sub_dir) if sub_dir else vendor_dir
        gs_exe = os.path.join(gs_dir, 'gswin64c.exe')
        if os.path.isfile(gs_exe):
            binaries.append((gs_exe,
                             os.path.join('vendor', 'ghostscript', sub_dir) if sub_dir else 'vendor/ghostscript'))
            # 收集 DLL 文件
            for f in os.listdir(gs_dir):
                if f.endswith('.dll'):
                    binaries.append((os.path.join(gs_dir, f),
                                     os.path.join('vendor', 'ghostscript', sub_dir) if sub_dir else 'vendor/ghostscript'))
            # 收集 lib 目录（Ghostscript 资源文件）
            lib_dir = os.path.join(gs_dir, 'lib')
            if os.path.isdir(lib_dir):
                datas.append((lib_dir,
                              os.path.join('vendor', 'ghostscript', sub_dir, 'lib') if sub_dir
                              else os.path.join('vendor', 'ghostscript', 'lib')))
            break

# ========== 构建配置 ==========
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

# ========== 可执行文件 ==========
exe_options = dict(
    pyz=pyz,
    scripts=a.scripts,
    strip=False,
    upx=True,
    console=True,         # 保留控制台窗口（用于日志输出）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if system == 'Darwin':
    # macOS: 生成 .app bundle
    exe_options['name'] = 'PDFCompressor'
    exe_options['exclude_binaries'] = True  # macOS COLLECT 需要
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
        icon=None,  # 可设置 .icns 图标文件路径
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
    # Windows/Linux: 生成单文件 exe
    exe_options['name'] = 'PDFCompressor'
    exe_options['icon'] = None  # 可设置 .ico 图标文件路径
    exe_options['binaries'] = a.binaries
    exe_options['zipfiles'] = a.zipfiles
    exe_options['datas'] = a.datas
    exe_options['exclude_binaries'] = False
    exe = EXE(**exe_options)
