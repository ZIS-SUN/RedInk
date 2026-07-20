# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 配置：把 RedInk 打包成 macOS 的 windowed .app
# 构建：uv run pyinstaller redink.spec --noconfirm

from PyInstaller.utils.hooks import collect_submodules

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
        # pywebview 在 macOS 上依赖 pyobjc / WebKit
        'objc',
        'Foundation',
        'AppKit',
        'WebKit',
        'Security',
        'CoreFoundation',
    ]
)

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
