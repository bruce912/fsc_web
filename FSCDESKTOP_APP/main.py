#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FSC 電子支付資料系統 — 桌面版入口
執行：python main.py
打包：pyinstaller build.spec
"""

import sys
import os
import threading
import time
import shutil
from pathlib import Path

# ── 路徑設定（區分開發模式 vs PyInstaller 打包後） ──────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller 打包後，原始資源在此資料夾
    BUNDLE_DIR = Path(sys._MEIPASS)
    # 使用者資料存 %APPDATA%\FSCTool，可讀寫
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "FSCTool"
else:
    BUNDLE_DIR = Path(__file__).parent
    DATA_DIR = Path(__file__).parent

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_DEST = DATA_DIR / "fsc_ebank.db"
DB_SRC  = BUNDLE_DIR / "fsc_ebank.db"
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 首次執行時，將初始資料庫複製到使用者資料目錄
if not DB_DEST.exists() and DB_SRC.exists():
    shutil.copy2(DB_SRC, DB_DEST)

# 注入環境變數給 web_app.py 讀取
os.environ["FSC_DB_PATH"]     = str(DB_DEST)
os.environ["FSC_UPLOAD_DIR"]  = str(UPLOAD_DIR)
os.environ["FSC_BUNDLE_DIR"]  = str(BUNDLE_DIR)

# ── 載入 Flask app ────────────────────────────────────────────────────────────
import web_app  # noqa: E402  (必須在環境變數設定後才 import)

PORT = 5678  # 桌面版用不同 port，避免與開發版衝突

def run_flask():
    web_app.app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)

def wait_for_server(timeout=10):
    import urllib.request
    url = f"http://127.0.0.1:{PORT}/"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False

# ── 啟動 Flask 執行緒 ─────────────────────────────────────────────────────────
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

if not wait_for_server():
    print("Flask 伺服器啟動逾時，請檢查 port 是否被佔用。")
    sys.exit(1)

# ── 開啟 pywebview 視窗 ───────────────────────────────────────────────────────
import webview  # noqa: E402

window = webview.create_window(
    title="FSC 電子支付資料系統",
    url=f"http://127.0.0.1:{PORT}/",
    width=1280,
    height=800,
    min_size=(900, 600),
    resizable=True,
    text_select=True,
)

webview.start(debug=False)
