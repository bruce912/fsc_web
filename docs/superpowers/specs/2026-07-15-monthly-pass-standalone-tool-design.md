# Windows 月票單機工具設計

## 目標

建立一個可在 Windows 單機執行的月票工具，輸出為資料夾版 `MonthlyPassTool.exe`。工具只包含「行政院月票交易統計」檢視與「月票 Excel 匯入」，並在輸出資料夾附帶目前的 `fsc_ebank.db`，讓使用者雙擊後即可查看既有資料，之後也能匯入新版月票報表更新資料。

## 非目標

- 不包含一般 FSC 電子支付資料瀏覽、儀表板、月份比較、趨勢圖、全業者統計、欄位說明或 AI 查詢。
- 不包含 ebank JSON/CSV 申報資料匯入。
- 不包含 LINE Pay 脫鉤監控 PDF 匯入。
- 不改變現有主系統 `launcher.py`、`web_app.py`、Cloudflare Pages 或 Render 部署流程。
- 不做 PyInstaller one-file 輸出。SQLite 資料庫需放在 exe 同層，方便讀寫、備份與替換。

## 使用者體驗

使用者取得 `dist/MonthlyPassTool/` 後，雙擊 `MonthlyPassTool.exe`。程式在本機啟動 Flask server，並用 pywebview 開啟桌面視窗。畫面只顯示月票工具，不出現其他 FSC 系統頁面。

工具包含兩個主要工作區：

1. 月票統計
   - 月份選擇。
   - 合計交易筆數、交易金額、方案數等 KPI。
   - SVC、QR、合計的體系別統計與前月比較。
   - SVC / QR 近 6 月交易筆數與交易金額曲線圖。
   - 本月 Top 5 方案排行、方案佔比、方案明細表。
   - Top 5 方案月份彙整表。

2. 月票 Excel 匯入
   - 只接受 `.xlsx`。
   - 支援拖曳或點選上傳。
   - 匯入完成後顯示新增、更新、跳過筆數。
   - 匯入成功後刷新月票統計與匯入紀錄。
   - 匯入紀錄只顯示 `月票交易統計` 最近 50 筆。

## 架構

新增獨立入口與 app factory，主系統維持原樣。

```text
FSCWEB/
├── monthly_pass_launcher.py
├── monthly_pass_tool.spec
├── build_monthly_pass_tool.bat
├── src/fsctool/monthly_pass_app.py
├── templates/monthly_pass_tool.html
├── static/js/monthly-pass.js
├── static/js/core.js
├── static/css/app.css
└── fsc_ebank.db
```

### `monthly_pass_launcher.py`

- 專用桌面入口。
- 尋找可用本機 port。
- 背景執行 `create_monthly_pass_app()`。
- 等待 server 就緒後用 pywebview 開窗。
- 視窗標題使用「行政院月票交易統計工具」。

### `src/fsctool/monthly_pass_app.py`

提供專用 Flask app factory，不註冊主系統其他 blueprint。

路由：

- `GET /`：回傳 `monthly_pass_tool.html`。
- `GET /health`：回傳 `{ "status": "ok" }`。
- `GET /api/monthly_pass/periods`
- `GET /api/monthly_pass/schemes`
- `GET /api/monthly_pass/by_system`
- `GET /api/monthly_pass/by_scheme`
- `GET /api/monthly_pass/trend`
- `GET /api/monthly_pass/latest_summary`
- `GET /api/monthly_pass/scheme_monthly`
- `POST /api/monthly_pass/import`
- `GET /api/monthly_pass/import_log`

月票查詢 API 可沿用現有 SQL 行為，但應移到專用模組或薄 wrapper，避免專用工具 import 整個 `web_legacy.py` 後連帶帶入 PDF、AI、一般匯入等不需要的依賴。

### 模板與前端

`monthly_pass_tool.html` 使用現有 Bootstrap、Bootstrap Icons、Chart.js、`app.css`、`core.js` 與 `monthly-pass.js` 的月票能力，但只載入月票工具需要的 DOM。

需要新增或調整一個輕量 JS 入口，例如 `monthly-pass-tool.js`：

- 初始化月票頁。
- 綁定 `.xlsx` 拖曳與上傳。
- 呼叫 `POST /api/monthly_pass/import`。
- 匯入完成後重新呼叫 `initMonthlyPass()` 或專用 refresh 函式。

避免載入 `dashboard.js`、`browse.js`、`imports.js`、`industry.js`、`details.js`、`docs.js` 等主系統功能檔。

## 資料庫與資料流

### 資料庫位置

- 開發模式預設使用 `FSCWEB/fsc_ebank.db`。
- PyInstaller frozen 模式使用 `Path(sys.executable).parent / "fsc_ebank.db"`。
- 打包腳本把目前 `FSCWEB/fsc_ebank.db` 複製到 `dist\MonthlyPassTool\fsc_ebank.db`。
- 若 exe 同層沒有 `fsc_ebank.db`，啟動仍可成功，但月票 API 回傳空資料，使用者可先匯入 Excel 建立資料。

### Excel 匯入

`POST /api/monthly_pass/import` 流程：

1. 驗證 request 內有 `file`。
2. 驗證副檔名為 `.xlsx`。
3. 使用 `openpyxl.load_workbook(..., read_only=True, data_only=True)` 解析。
4. 每個 worksheet 第一列需包含核心欄位：
   - `方案代碼`
   - `方案名稱`
   - `體系別`
   - `交易筆數`
   - `交易金額`
   - `統計年月`
   - `資料最後更新日期`
5. 支援既有別名 `案代碼` 對應到 `方案代碼`。
6. 正規化：
   - `方案代碼` 補成 2 位字串。
   - `統計年月` 轉成 6 位西元年月字串。
   - 衍生 `yr`、`mn`、`ym`，其中 `yr = 西元年 - 1911`，`ym = 民國年/月`。
   - `交易筆數` 與 `交易金額` 儘量轉整數。
   - `資料最後更新日期` 轉字串並移除不必要空白。
7. 呼叫 `record_loader.upsert_records(conn, "月票交易統計", records, skip_fields)`。
8. 使用自然鍵 `統計年月 + 方案代碼 + 體系別` 進行 insert/update/unchanged。
9. 寫入 `_import_log`。
10. 回傳匯入結果。

### 首次建表

若 DB 內不存在 `月票交易統計`，匯入流程會由 `record_loader.upsert_records` 依 Excel 欄位建立資料表，並補上 `_source_key`、`_source_hash` 與唯一索引。

## 錯誤處理

- 無檔案：回傳 400 與「請選擇檔案」。
- 空檔名：回傳 400 與「空檔名」。
- 非 `.xlsx`：回傳 400 與「僅支援月票 Excel .xlsx 檔案」。
- Excel 無核心欄位或無可匯入資料：回傳 400 與「Excel 中找不到月票交易資料（請確認格式正確）」。
- `統計年月` 無法轉換：跳過該列；若全部列都無法轉換，視為無可匯入資料。
- SQLite 或 upsert 失敗：rollback，回傳 500 與錯誤訊息。
- 查詢時資料表不存在：月票查詢 API 回傳空陣列或空物件，不讓頁面崩潰。

## 打包

新增 `monthly_pass_tool.spec`：

- entrypoint：`monthly_pass_launcher.py`。
- app name：`MonthlyPassTool`。
- `console=False`。
- `pathex=[".", "src"]`。
- hidden imports 至少包含 Flask、Werkzeug、Jinja2、openpyxl、pywebview、fsctool。
- datas 包含：
  - `templates/monthly_pass_tool.html`
  - 必要 static CSS/JS/font 資源
  - pywebview data files
- 不把 `fsc_ebank.db` 打進 exe；由 bat 複製到 dist 資料夾。

新增 `build_monthly_pass_tool.bat`：

1. 檢查 Python。
2. 安裝必要套件：Flask、Werkzeug、openpyxl、pywebview、pyinstaller。
3. 清理 `dist\MonthlyPassTool` 與 `build`。
4. 執行 `pyinstaller monthly_pass_tool.spec --noconfirm`。
5. 複製 `fsc_ebank.db` 到 `dist\MonthlyPassTool\fsc_ebank.db`。
6. 顯示輸出路徑與發布方式。

## 測試計畫

新增或擴充 Python 測試：

- Excel parser 能解析目前範例 `行政院月票交易統計報表(for+金管會) 2.xlsx`。
- 空白 SQLite 匯入後會建立 `月票交易統計`。
- 同一份 Excel 重複匯入會產生 unchanged，而不是重複列。
- 同自然鍵內容變動時會更新既有列。
- `GET /` 回傳專用工具頁。
- 月票 API 在空 DB 時回傳空資料但 status 200。
- 匯入 API 拒絕非 `.xlsx`。
- 匯入成功後 `_import_log` 只回傳月票匯入紀錄。

本機 smoke test：

- 在 macOS 開發環境用 Python 啟動專用 app，確認頁面可載入。
- 用範例 `.xlsx` 呼叫匯入 API，確認查詢 API 有資料。
- Windows `.exe` 需在 Windows 或可用的 Windows PyInstaller 環境執行 `build_monthly_pass_tool.bat` 驗證。

## 實作順序

1. 抽出月票 Excel parser、import service、query service，避免依賴整個 `web_legacy.py`。
2. 新增 `monthly_pass_app.py` 與 API tests。
3. 新增專用模板與輕量 JS 入口。
4. 新增 `monthly_pass_launcher.py`。
5. 新增 PyInstaller spec 與 Windows bat。
6. 跑測試與本機 app smoke。

## 接受條件

- 執行專用 app 後只看到月票統計與月票 Excel 匯入。
- `.xlsx` 匯入成功後，統計圖表與表格能顯示新資料。
- 重複匯入不產生重複列。
- `dist\MonthlyPassTool\MonthlyPassTool.exe` 與同層 `fsc_ebank.db` 為發布單位。
- 主系統入口與既有功能不因本工具改動而失效。
