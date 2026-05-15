#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_disclosure_zip.py
------------------------
將金管會電子支付帳戶重要資訊揭露 ZIP 檔 (BB-YYMM_*.zip) 解析後，
寫入 fsc_ebank.db 的「全業者統計」資料表。

支援格式：
  ZIP 內含 YYMM_電子支付帳戶重要資訊揭露.xlsx
  欄位（A~H）：
    A 電子支付機構名稱
    B 使用者人數
    C 當月代理收付實質交易款項金額
    D 當月辦理國內外小額匯兌金額
    E 當月收受儲值款項金額
    F 儲值款項餘額
    G 代理收付款項餘額
    H 合計

用法：
  python3 import_disclosure_zip.py                   # 處理當前目錄所有 BB-*.zip
  python3 import_disclosure_zip.py BB-1151_*.zip     # 指定檔案
"""

import sys
import re
import io
import zipfile
import sqlite3
import glob
from pathlib import Path

try:
    import openpyxl
except ImportError:
    sys.exit("❌ 請先安裝 openpyxl：pip install openpyxl")

# ── 設定路徑 ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "fsc_ebank.db"

# 民國年 → 西元年
def roc_to_ad(roc_yr: int) -> int:
    return roc_yr + 1911

def parse_roc_ym(text: str):
    """解析 '115年1月' → (115, 1)  回傳民國年"""
    m = re.search(r'(\d+)年(\d+)月', str(text))
    if not m:
        raise ValueError(f"無法解析年月：{text!r}")
    return int(m.group(1)), int(m.group(2))

def to_float(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(',', '').strip())
    except Exception:
        return None

# ── 解析單一 ZIP ─────────────────────────────────────────────────
def parse_zip(zip_path: Path):
    """
    回傳 list of dict，每個 dict 對應一筆機構資料：
      yr, mn, ym, 機構名稱, 使用者人數,
      代理收付金額_千元, 移轉匯兌金額_千元, 欄位說明,
      收受儲值金額_千元, 儲值餘額_千元, 代理收付餘額_千元, 各類餘額合計_千元
    """
    with zipfile.ZipFile(zip_path) as zf:
        xlsx_names = [n for n in zf.namelist() if n.lower().endswith('.xlsx')]
        if not xlsx_names:
            raise FileNotFoundError(f"{zip_path.name} 內找不到 .xlsx 檔")
        xlsx_data = zf.read(xlsx_names[0])

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_data), data_only=True)
    ws = wb.active

    # ── 找資料月份（row 3，D 欄）────────────────────────────────
    roc_yr, mn = None, None
    for row in ws.iter_rows(min_row=1, max_row=6, values_only=True):
        for cell in row:
            if cell and re.search(r'\d+年\d+月', str(cell)):
                roc_yr, mn = parse_roc_ym(str(cell))
                break
        if roc_yr:
            break

    if roc_yr is None:
        raise ValueError(f"{zip_path.name}：找不到資料月份")

    yr_ad = roc_to_ad(roc_yr)
    ym    = f"{roc_yr}/{mn:02d}"          # 保持與既有格式一致（民國年/月）
    print(f"  月份：{roc_yr}年{mn}月  →  yr={roc_yr}, mn={mn}, ym={ym}")

    # ── 解析資料行（row 6 起，直到碰到「總計」或空白機構名）────────
    records = []
    SKIP_NAMES = {'總計', '合計', None, ''}
    STOP_PREFIXES = ('一、', '二、', '注：', '說明', '備註')

    for row in ws.iter_rows(min_row=6, values_only=True):
        org = row[0]
        if org is None:
            continue
        org = str(org).strip()
        if not org or org in SKIP_NAMES:
            continue
        if any(org.startswith(p) for p in STOP_PREFIXES):
            break

        records.append({
            'yr':              roc_yr,
            'mn':              mn,
            'ym':              ym,
            '機構名稱':        org,
            '使用者人數':      to_float(row[1]),
            '代理收付金額_千元':  to_float(row[2]),
            '移轉匯兌金額_千元':  to_float(row[3]),
            '欄位說明':        '國內外小額匯兌',   # 新格式固定值
            '收受儲值金額_千元':  to_float(row[4]),
            '儲值餘額_千元':   to_float(row[5]),
            '代理收付餘額_千元':  to_float(row[6]),
            '各類餘額合計_千元':  to_float(row[7]),
        })

    print(f"  解析到 {len(records)} 筆機構資料")
    return records

# ── 寫入 DB ──────────────────────────────────────────────────────
INSERT_SQL = '''
INSERT INTO "全業者統計"
  (yr, mn, ym, 機構名稱, 使用者人數,
   代理收付金額_千元, 移轉匯兌金額_千元, 欄位說明,
   收受儲值金額_千元, 儲值餘額_千元, 代理收付餘額_千元, 各類餘額合計_千元)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
'''

def records_to_rows(records):
    return [
        (
            r['yr'], r['mn'], r['ym'], r['機構名稱'],
            r['使用者人數'], r['代理收付金額_千元'], r['移轉匯兌金額_千元'],
            r['欄位說明'],
            r['收受儲值金額_千元'], r['儲值餘額_千元'],
            r['代理收付餘額_千元'], r['各類餘額合計_千元'],
        )
        for r in records
    ]

def import_to_db(all_records: list, db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    inserted_total = 0
    skipped_total  = 0

    # 逐月處理，先刪再插（冪等操作）
    by_ym = {}
    for r in all_records:
        by_ym.setdefault((r['yr'], r['mn'], r['ym']), []).append(r)

    for (yr, mn, ym), records in sorted(by_ym.items()):
        # 檢查是否已有此月份資料
        existing = conn.execute(
            'SELECT COUNT(*) FROM "全業者統計" WHERE yr=? AND mn=?',
            (yr, mn)
        ).fetchone()[0]

        if existing > 0:
            print(f"  ⚠️  {ym} 已有 {existing} 筆資料，覆寫中...")
            conn.execute(
                'DELETE FROM "全業者統計" WHERE yr=? AND mn=?',
                (yr, mn)
            )
            skipped_total += existing

        rows = records_to_rows(records)
        conn.executemany(INSERT_SQL, rows)
        inserted_total += len(rows)
        print(f"  ✅ {ym}  插入 {len(rows)} 筆")

    conn.commit()
    conn.close()
    return inserted_total, skipped_total

# ── 主流程 ───────────────────────────────────────────────────────
def main():
    # 決定要處理哪些 ZIP
    if len(sys.argv) > 1:
        zip_paths = [Path(p) for p in sys.argv[1:]]
    else:
        # 自動找當前目錄下所有 BB-*.zip
        zip_paths = sorted(BASE_DIR.glob("BB-*.zip"))

    if not zip_paths:
        sys.exit("❌ 找不到任何 BB-*.zip 檔案，請指定路徑或將檔案放在腳本同目錄。")

    print(f"找到 {len(zip_paths)} 個 ZIP 檔：")
    for p in zip_paths:
        print(f"  {p.name}")
    print()

    if not DB_PATH.exists():
        sys.exit(f"❌ 資料庫不存在：{DB_PATH}")

    all_records = []
    for zp in zip_paths:
        print(f"📂 處理：{zp.name}")
        try:
            records = parse_zip(zp)
            all_records.extend(records)
        except Exception as e:
            print(f"  ❌ 失敗：{e}")
        print()

    if not all_records:
        sys.exit("❌ 沒有解析到任何資料。")

    print(f"共解析 {len(all_records)} 筆，開始寫入 {DB_PATH.name}...")
    inserted, skipped = import_to_db(all_records, DB_PATH)

    print(f"\n✅ 完成！插入 {inserted} 筆，覆寫舊資料 {skipped} 筆。")

    # 驗證
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute('SELECT COUNT(*) FROM "全業者統計"').fetchone()[0]
    latest = conn.execute(
        'SELECT yr, mn, COUNT(*) FROM "全業者統計" GROUP BY yr, mn ORDER BY yr DESC, mn DESC LIMIT 5'
    ).fetchall()
    conn.close()
    print(f"資料庫全業者統計總計：{total} 筆")
    print("最新 5 個月份：")
    for row in latest:
        print(f"  {row[0]}年{row[1]:02d}月  {row[2]} 筆")


if __name__ == "__main__":
    main()
