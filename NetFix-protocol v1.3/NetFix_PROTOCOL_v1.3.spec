# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('logo.ico', '.'), ('settings.json', '.')],
    hiddenimports=['customtkinter', 'PIL', 'matplotlib', 'winshell', 'win32gui', 'win32api', 'win32con', 'webview', 'webview.platforms.edgechromium', 'wifi', 'config', 'utils', 'chart_widget', 'settings_windows', 'tray_icon', 'v2ray_manager', 'v2ray_paths', 'v2ray_config', 'v2ray_profiles', 'v2ray_subscription', 'v2ray_ping', 'v2ray_proxy_windows', 'v2ray_core', 'v2ray_window'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NetFix_PROTOCOL_v1.3',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
