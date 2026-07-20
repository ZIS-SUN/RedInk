# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置：按平台打包 RedInk 桌面版
# - macOS：windowed .app（BUNDLE）
# - Windows：windowed RedInk.exe（COLLECT 目录，未经真机验证）
# 构建：uv run pyinstaller redink.spec --noconfirm

import sys

from PyInstaller.utils.hooks import collect_submodules

IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'

block_cipher = None

# 只读资源：目标相对路径必须与 backend/paths.py 中 resource_path() 的调用一致
# - resource_path('frontend/dist')
# - resource_path('backend/prompts/xxx.txt')
# - resource_path('text_providers.yaml.example') / resource_path('image_providers.yaml.example')
datas = [
    ('frontend/dist', 'frontend/dist'),
    ('backend/prompts', 'backend/prompts'),
    ('text_providers.yaml.example', '.'),
    ('image_providers.yaml.example', '.'),
]

hiddenimports = (
    collect_submodules('backend')
    + collect_submodules('webview')
    + [
        # Flask 生态
        'flask',
        'flask_cors',
        'yaml',
        'requests',
        'dotenv',
        # 图片处理
        'PIL',
        'PIL.Image',
    ]
)

if IS_MACOS:
    # pywebview 在 macOS 上依赖 pyobjc / WebKit
    hiddenimports += [
        'objc',
        'Foundation',
        'AppKit',
        'WebKit',
        'Security',
        'CoreFoundation',
    ]
elif IS_WINDOWS:
    # pywebview 在 Windows 上默认走 EdgeChromium（WebView2）后端：
    # webview.platforms.winforms / edgechromium 已由 collect_submodules('webview')
    # 覆盖，但底层的 pythonnet / clr 桥接是动态导入，PyInstaller 静态分析
    # 发现不了，必须显式声明（见 pywebview 冻结文档与 issue #225 / #1316）。
    hiddenimports += [
        'clr',
        'clr_loader',
        'pythonnet',
    ]

# Windows 图标：仓库中暂无 .ico 文件。可用 scripts/make_icns.py 的姊妹脚本
# （scripts/make_ico.py，待创建）从 images/logo.png 生成 build/icon.ico，
# 生成后把下面的 icon 参数指向它（详见 BUILD_DESKTOP.md「Windows 构建」）。
_WINDOWS_ICON = 'build/icon.ico'  # 占位路径：文件存在时才传给 EXE

if IS_WINDOWS:
    import os

    _exe_icon = _WINDOWS_ICON if os.path.exists(_WINDOWS_ICON) else None
else:
    _exe_icon = None

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RedInk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='RedInk',
)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name='RedInk.app',
        # 由 scripts/make_icns.py 从 images/logo.png 生成
        icon='build/icon.icns',
        bundle_identifier='com.redink.desktop',
        info_plist={
            'CFBundleName': 'RedInk',
            'CFBundleDisplayName': '红墨 RedInk',
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
            # 允许 http://127.0.0.1 本地明文请求
            'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        },
    )
