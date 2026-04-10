# FSC 電子支付資料 Web 系統

金融監督管理委員會（FSC）電子支付業務統計資料查詢與管理平台，支援本機執行與雲端部署（Render）。

---

## 功能概覽

- 瀏覽、查詢電子支付各類統計報表（27 種資料表）
- 上傳 JSON 增量資料自動匯入 SQLite 資料庫
- 匯出 CSV / Excel 格式報表
- 行政院月票方案交易統計整合
- 支援 Render 雲端一鍵部署

---

## 專案結構

```
FSCWEB/
├── web_app.py          # Flask 主應用程式
├── build_database.py   # 資料庫初始化 / 建置腳本
├── migrate_database.py # 資料庫版本遷移腳本
├── launcher.py         # 桌面版啟動器（pywebview）
├── fsc_ebank.db        # SQLite 資料庫
├── requirements.txt    # Python 相依套件
├── render.yaml         # Render 雲端部署設定
├── start.sh            # Linux/macOS 快速啟動腳本
├── build.bat           # Windows 打包腳本（PyInstaller）
├── templates/
│   └── index.html      # 前端頁面
├── static/
│   ├── css/            # 樣式檔
│   └── js/             # 前端邏輯
└── uploads/            # 上傳的 JSON 暫存目錄
```

---

## 本機執行

### 環境需求

- Python 3.9+

### 安裝步驟

```bash
# 1. 安裝相依套件
pip install -r requirements.txt

# 2. 啟動伺服器
python3 web_app.py
```

開啟瀏覽器前往：[http://127.0.0.1:5000](http://127.0.0.1:5000)

或使用快速啟動腳本（macOS / Linux）：

```bash
bash start.sh
```

---

## 資料更新流程

### 步驟 1：從 ebank 網站抓取資料

使用專案根目錄的 `ebank_monthly_updater.js` 腳本（Chrome DevTools Snippets）自動下載增量 JSON 檔案。詳細操作請參閱 [使用說明.md](../使用說明.md)。

### 步驟 2：上傳資料至系統

在 Web 介面上傳 JSON 檔案，系統會自動解析並匯入資料庫，避免重複匯入。

---

## 雲端部署（Render）

本專案已包含 `render.yaml`，可直接部署至 [Render](https://render.com)。

```yaml
runtime: python
buildCommand: pip install -r requirements.txt
startCommand: gunicorn web_app:app --bind 0.0.0.0:$PORT
```

**部署步驟：**

1. 將程式碼 push 到 GitHub
2. 在 Render 建立新的 Web Service，選擇此 repo
3. Render 會自動讀取 `render.yaml` 完成設定

---

## 支援的資料表

| 代碼 | 說明 |
|------|------|
| EC002W | 儲值卡發行資料 |
| EC011W | 儲值卡類型 |
| EP005B | 電支帳戶戶數／人數 |
| EP005W | 電支帳戶使用者別交易 |
| EP006B | 業務帳戶別交易 |
| EP006W | 業務別交易 |
| EP007W | 電支帳戶支付工具別交易 |
| EP007X | 儲值卡支付工具別交易 |
| EP008W | 特約機構交易 |
| EP010W | 實體通路支付服務 |
| EP010X | 代理收付通路別交易 |
| EP014W | 收受支付款項餘額 |
| EP015W | 申訴案件統計 |
| EP105B | 境外業務客戶數 |
| EP105W | 境外業務客戶 |
| EP106B | 境外業務客戶交易 |
| EP106W | 境外業務業務別交易 |
| EP106X | 與大陸地區合作業務 |
| EP107W | 境外業務支付工具 |
| EP108W | 境外業務收款方交易 |
| EP108X | 境外業務付款方交易 |
| EP114W | 境外業務餘額 |
| EP115W | 境外業務申訴 |
| WB031W | 電話申訴辦理 |
| WB032W | 申訴服務專線 |
| WB033W | 人民陳情案件 |
| WB041W | 行動支付業務 |
| WB056W | 端末設備共用 |
| 月票交易統計 | 行政院月票方案交易統計 |

---

## 技術棧

- **後端**：Python / Flask / SQLite
- **前端**：HTML / CSS / JavaScript
- **部署**：Gunicorn / Render
- **桌面版**：PyInstaller + pywebview
