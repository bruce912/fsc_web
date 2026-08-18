# FSC 電子支付資料 Web 系統

金融監督管理委員會（FSC）電子支付業務統計資料查詢與管理平台。正式環境為 Cloudflare Pages 靜態網站；Flask 版本保留供本機資料管理與開發使用。

> 最新正式架構、每月更新、GitHub Actions、Cloudflare 部署與故障排除，請參閱
> [系統架構與維護手冊](./系統架構與維護手冊.md)。

---

## 功能概覽

- 瀏覽、查詢電子支付各類統計報表（27 種資料表）
- 全業者統計公開資料自動更新
- 上傳 JSON 增量資料自動匯入 SQLite 資料庫
- 匯出 CSV / Excel 格式報表
- 行政院月票方案交易統計整合
- GitHub Actions 排程與 Cloudflare Pages 自動部署

---

## 專案結構

```
FSCWEB/
├── web_app.py          # Flask 主應用程式
├── build_database.py   # 資料庫初始化 / 建置腳本
├── migrate_database.py # 資料庫版本遷移腳本
├── update_industry_stats.py # 全業者統計公開資料自動更新
├── import_disclosure_zip.py # 公開揭露 ZIP 匯入
├── export_static_site.py    # SQLite / Flask → 靜態網站
├── launcher.py         # 桌面版啟動器（pywebview）
├── fsc_ebank.db        # SQLite 資料庫
├── requirements.txt    # Python 相依套件
├── static_site/        # Cloudflare Pages 部署內容
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

## 舊版動態部署（Render，非目前正式環境）

本專案仍保留 `render.yaml`，可部署動態 Flask 版本至 [Render](https://render.com)，但目前正式網站使用 Cloudflare Pages。

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

## 正式靜態網站輸出

靜態版保留儀表板、資料瀏覽、月份比較、趨勢、全業者統計、月票統計、文件與 CSV 匯出；資料匯入及 Ollama 聊天仍只在本機 Flask 版本提供。

```bash
# 先建立最新版 SQLite
python3 build_database.py

# 輸出至 FSCWEB/static_site/
python3 export_static_site.py

# 本機預覽
python3 -m http.server 8001 --directory static_site
```

開啟 [http://127.0.0.1:8001](http://127.0.0.1:8001)。每月更新資料庫後重新執行 `export_static_site.py` 即可產生新版靜態資料。

### 全業者統計自動更新

公開揭露資料不需登入，可直接檢查金管會最新 ZIP、匯入 SQLite，並同步歷史 CSV：

```bash
# 只檢查是否有新月份
python3 update_industry_stats.py --dry-run

# 下載資料庫最新月份之後的新資料並匯入
python3 update_industry_stats.py
python3 export_static_site.py
```

GitHub Actions 會在每月 12、19 日自動檢查，也可在 Actions 頁面手動執行
`Update FSC industry statistics`。若設定 `CLOUDFLARE_API_TOKEN` 與
`CLOUDFLARE_ACCOUNT_ID` repository secrets，資料有變動時會自動重新部署 Pages。

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
- **正式部署**：GitHub Actions / Cloudflare Pages
- **舊版動態部署**：Gunicorn / Render
- **桌面版**：PyInstaller + pywebview
