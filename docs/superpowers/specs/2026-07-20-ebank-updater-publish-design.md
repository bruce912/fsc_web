# ebank_monthly_updater 資料庫發布設計

日期：2026-07-20

## 目標

將 `FSCWEB/ebank_monthly_updater.py` 從「只抓取 ebank 各資料表並輸出 JSON」升級為完整更新入口。使用者執行同一支 Python 程式後，可選擇只產生 JSON，或在抓取完成後自動合併、驗證、備份並發布到網站使用的 `fsc_ebank.db`。

## 不做的事

- 不改變 ebank 登入方式；圖形驗證碼仍由使用者在瀏覽器完成。
- 不把帳號、密碼、cookie 或瀏覽器 profile 寫入版本控制。
- 不在資料抓取失敗時覆蓋正式資料庫。
- 不把金管會公開揭露 ZIP 匯入混進這次 scope；那是 `import_disclosure_zip.py` 既有職責。

## 使用方式

保留既有模式：

```bash
python ebank_monthly_updater.py
```

此模式只抓取資料並輸出 `ebank_update_<yr>_<mn>.json`。

新增發布模式：

```bash
python ebank_monthly_updater.py --update-db
```

此模式在 JSON 輸出成功後，繼續執行資料庫更新流程。

可搭配既有參數：

```bash
python ebank_monthly_updater.py --reset --months 6 --update-db
python ebank_monthly_updater.py --dry-run
```

`--dry-run` 仍只列出將處理的資料表，不更新資料庫。

## 資料流程

```text
登入 ebank
  -> 逐表抓取 DataTable 列表
  -> 逐筆抓取明細
  -> 輸出 ebank_update_*.json
  -> 呼叫資料庫更新流程
  -> 合併歷史 JSON
  -> 建立候選 SQLite
  -> 驗證完整性、資料表與月份
  -> 備份正式 fsc_ebank.db
  -> 原子替換正式資料庫
```

## 元件邊界

`ebank_monthly_updater.py`

- 負責登入、導覽、抓取與輸出 JSON。
- 新增 `--update-db` 參數。
- 抓取成功且 `total_new > 0` 時，才觸發資料庫更新。
- 若資料庫更新失敗，回報錯誤並保留 JSON 檔。

`update_pipeline.py` 或既有建庫流程

- 負責合併 JSON、建候選資料庫、驗證、備份與發布。
- `ebank_monthly_updater.py` 不直接操作正式 DB 內容，避免責任混雜。

`run_monthly_update.command`

- 改為呼叫 `ebank_monthly_updater.py --update-db`。
- 使用者雙擊後的結果應是一條龍更新到網站資料庫。

## 錯誤處理

- 任一資料表抓取失敗時，仍輸出已成功抓到的資料，但不自動發布，除非未來明確加入 `--allow-partial-publish`。
- 若沒有新資料，不產生 JSON，也不跑資料庫更新。
- 若資料庫驗證失敗，正式 `fsc_ebank.db` 保持原狀。
- 若更新流程出錯，命令以非零狀態結束，方便排程或 LaunchAgent 判定失敗。

## 驗證

至少完成：

- `python ebank_monthly_updater.py --dry-run`
- 單元或 smoke 測試確認 `--update-db` 會在 JSON 成功後呼叫更新流程。
- 失敗情境測試：更新流程回傳失敗時不刪除 JSON，不更新狀態為成功。
- 若專案內已有 `update_pipeline.py`，執行 `python update_pipeline.py --no-publish` 驗證資料建庫流程。

## 成功條件

- 使用者可用同一支 `ebank_monthly_updater.py` 完成抓取與資料庫發布。
- 預設不破壞既有行為；未加 `--update-db` 時仍只輸出 JSON。
- 正式資料庫只在完整驗證通過後才替換。
- 文件與雙擊腳本都指向新的更新入口。
