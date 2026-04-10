# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包設定
# 用法：pyinstaller build.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

added_files = [
    ("templates",    "templates"),     # Jinja2 模板
    ("static",       "static"),        # 靜態資源 (CSS/JS)
    ("fsc_ebank.db", "."),             # 初始資料庫（首次執行時複製到 AppData）
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "flask",
        "werkzeug",
        "jinja2",
        "click",
        "webview",
        "webview.platforms.winforms",  # Windows 平台
        "clr",
        "sqlite3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["gunicorn"],
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
    name="FSC電子支付資料系統",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # 不顯示 cmd 視窗
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # 如有圖示可取消註解
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FSC電子支付資料系統",  # 輸出資料夾名稱
)
