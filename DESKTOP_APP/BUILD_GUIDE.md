# FSC 電子支付資料系統 — 桌面版打包指南

## 目錄結構

```
DESKTOP_APP/
├── main.py          ← 桌面版入口（啟動 Flask + pywebview）
├── web_app.py       ← Flask 主程式（已修改路徑邏輯）
├── build.spec       ← PyInstaller 打包設定
├── requirements.txt ← 相依套件
├── fsc_ebank.db     ← 初始資料庫
├── templates/
└── static/
```

## 環境準備（Windows，需 Python 3.10+）

```bat
pip install -r requirements.txt
```

## 開發模式執行

```bat
python main.py
```

## 打包成 .exe

```bat
pyinstaller build.spec
```

輸出位置：`dist\FSC電子支付資料系統\FSC電子支付資料系統.exe`

## 使用者資料位置

打包後的程式，使用者資料（DB、上傳檔案）存放於：

```
C:\Users\{使用者名稱}\AppData\Roaming\FSCTool\
├── fsc_ebank.db   ← 使用者資料庫（首次執行自動建立）
└── uploads\       ← 上傳暫存
```

## 系統需求

| 項目 | 需求 |
|------|------|
| 作業系統 | Windows 10 / 11 |
| WebView2 | 內建於 Win10/11，無需另裝 |
| .NET Runtime | pywebview WinForms 需要（Win10/11 內建） |
| 磁碟空間 | ~150 MB（含 Python runtime） |

## 注意事項

- 不支援 Windows 7 / 8（缺少 WebView2）
- 首次啟動會將 `fsc_ebank.db` 複製到 AppData，之後的資料存在 AppData
- 更新程式不會覆蓋使用者的 AppData 資料庫
