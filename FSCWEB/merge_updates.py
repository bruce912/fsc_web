#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_updates.py
================
把 ebank_monthly_updater.py 產出的 `ebank_update_<yr>_<mn>.json` (bundle 格式)
合併成 `build_database.py` 預期的 `ebank_all_data_final.json` (dict 格式)。

同時：
- 若 ebank_json/JSON/ebank_<code>.json (per-item 歷史檔) 存在，會一併納入合併
  以確保歷史月份不會被刷掉。
- 產出 ebank_all_data.json 給 build_database.py 的 supplement 邏輯用 (內容同 final)
  讓 SUPPLEMENT_TABLES 也能拿到完整歷史。

去重 key：(yr, mn, sn)。同一筆若新舊都有，以「新檔 (update_*) 優先」。
"""
import json
import re
import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
PER_ITEM_DIR = BASE_DIR.parent / "ebank_json" / "JSON"

OUT_FINAL = BASE_DIR / "ebank_all_data_final.json"
OUT_OLD   = BASE_DIR / "ebank_all_data.json"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def record_key(r: dict):
    """去重 key：以 (yr, mn, sn) 為主；無年月者退用整列 JSON。"""
    yr, mn = r.get("yr"), r.get("mn")
    sn = r.get("sn")
    if yr is None and mn is None:
        return json.dumps(r, sort_keys=True, ensure_ascii=False)
    return (yr, mn, sn)


def merge_into(merged: dict, table_key: str, details: list, total_rows: Optional[int] = None):
    """把 details 加進 merged[table_key]，依 record_key 去重。"""
    if table_key not in merged:
        merged[table_key] = {"totalRows": total_rows or 0, "details": []}
    bucket = merged[table_key]
    existing = {record_key(r): i for i, r in enumerate(bucket["details"])}
    for r in details:
        k = record_key(r)
        if k in existing:
            # 已存在 — 新檔優先，覆蓋
            bucket["details"][existing[k]] = r
        else:
            existing[k] = len(bucket["details"])
            bucket["details"].append(r)
    if total_rows is not None and total_rows > bucket["totalRows"]:
        bucket["totalRows"] = total_rows


def collect_from_updates(merged: dict) -> int:
    """讀所有 ebank_update_*.json (bundle 格式)。回傳處理的檔案數。"""
    files = sorted(BASE_DIR.glob("ebank_update_*.json"))
    for f in files:
        try:
            payload = load_json(f)
        except Exception as e:
            print(f"  [WARN] 讀取失敗 {f.name}: {e}", file=sys.stderr)
            continue
        data = payload.get("data") or {}
        for table_key, td in data.items():
            details = td.get("details") or []
            if not details:
                continue
            merge_into(merged, table_key, details, td.get("totalRows"))
        print(f"  讀取 {f.name}: {len(data)} 表")
    return len(files)


# 從檔名 (如 ebank_EC002W.json) + 內容 itemName 還原完整 table_key
def collect_from_per_item(merged: dict) -> int:
    """讀 ebank_json/JSON/ebank_<code>.json (per-item 歷史檔)。"""
    if not PER_ITEM_DIR.exists():
        print(f"  (無歷史目錄 {PER_ITEM_DIR}，跳過)")
        return 0
    count = 0
    for f in sorted(PER_ITEM_DIR.glob("ebank_*.json")):
        # 跳過拷貝檔
        if re.search(r"拷貝", f.stem):
            continue
        # 跳過 bundle 格式檔（如 ebank_all_data.json、ebank_level2_all.json）
        if re.search(r"ebank_(all_data|level2_all)", f.stem):
            continue
        try:
            payload = load_json(f)
        except Exception as e:
            print(f"  [WARN] 讀取失敗 {f.name}: {e}", file=sys.stderr)
            continue
        # per-item 格式：{itemName, totalRows, details}
        table_key = payload.get("itemName")
        details   = payload.get("details") or []
        if not table_key or not details:
            continue
        merge_into(merged, table_key, details, payload.get("totalRows"))
        count += 1
    print(f"  讀取 {count} 個歷史 per-item JSON")
    return count


def main():
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"PER_ITEM_DIR: {PER_ITEM_DIR}")

    merged = {}

    print("\n[1/2] 讀取 ebank_update_*.json (本次抓取結果) ...")
    n_updates = collect_from_updates(merged)
    if n_updates == 0:
        print("  [WARN] 沒找到 ebank_update_*.json，請先跑 ebank_monthly_updater.py")

    print("\n[2/2] 讀取歷史 per-item JSON (補充歷史月份) ...")
    collect_from_per_item(merged)

    if not merged:
        print("\n[ERROR] 完全沒讀到資料，終止。", file=sys.stderr)
        sys.exit(1)

    # 依 yr DESC, mn DESC 排序每表的 details
    for table_key, bucket in merged.items():
        def sort_key(r):
            return (r.get("yr") or 0, r.get("mn") or 0)
        bucket["details"].sort(key=sort_key, reverse=True)
        # totalRows 用實際筆數覆蓋（避免顯示舊值誤導）
        bucket["totalRows"] = len(bucket["details"])

    # 寫出 final
    with open(OUT_FINAL, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    print(f"\n→ 已寫入 {OUT_FINAL.name}：{len(merged)} 表")

    # 寫出 old（內容同 final，讓 build_database.py 的 SUPPLEMENT 邏輯能正常運作）
    with open(OUT_OLD, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    print(f"→ 已寫入 {OUT_OLD.name} (供 SUPPLEMENT 邏輯使用，內容同 final)")

    # 摘要
    print("\n摘要：")
    for k in sorted(merged.keys()):
        n = len(merged[k]["details"])
        print(f"  {k[:50]:<50} {n:>5} 筆")


if __name__ == "__main__":
    main()
