#!/usr/bin/env python3
"""Download and import new FSC electronic-payment disclosure ZIP files."""

from __future__ import annotations

import argparse
import csv
import html
import io
import re
import sqlite3
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from import_disclosure_zip import import_to_db, parse_zip


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fsc_ebank.db"
CSV_PATH = BASE_DIR / "電子支付機構_全業者統計.csv"
DISCLOSURE_URL = (
    "https://www.banking.gov.tw/ch/home.jsp?id=591&parentpath=0,590&"
    "mcustomize=multimessage_view.jsp&dataserno=201805300001&dtable=Disclosure"
)
USER_AGENT = "fsc-web-monthly-updater/1.0 (+https://fsc-web.brucelab.org)"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(html.unescape(href))


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()


def period_from_url(url: str) -> tuple[int, int] | None:
    filename = unquote(Path(urlparse(url).path).name)
    match = re.search(r"(?:BB-)?(\d{3})(\d{1,2})(?=[^\d]|$)", filename, re.I)
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    return (year, month) if 1 <= month <= 12 else None


def disclosure_links(page: bytes) -> dict[tuple[int, int], str]:
    parser = LinkParser()
    parser.feed(page.decode("utf-8", errors="replace"))
    links: dict[tuple[int, int], str] = {}
    for href in parser.links:
        decoded = unquote(href).lower()
        if ".zip" not in decoded or "電子支付" not in decoded:
            continue
        url = urljoin(DISCLOSURE_URL, href)
        period = period_from_url(url)
        if period:
            links[period] = url
    return links


def existing_periods() -> set[tuple[int, int]]:
    with sqlite3.connect(DB_PATH) as conn:
        return {
            (int(year), int(month))
            for year, month in conn.execute(
                'SELECT DISTINCT yr, mn FROM "全業者統計"'
            )
        }


def append_csv(records: list[dict]) -> None:
    """Append newly imported periods without rewriting the historical CSV."""
    existing = set()
    if CSV_PATH.exists():
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as source:
            next(csv.reader(source), None)
            for row in csv.reader(source):
                if len(row) >= 2:
                    existing.add((row[0], row[1]))

    with CSV_PATH.open("a", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        for record in sorted(records, key=lambda item: (item["yr"], item["mn"], item["機構名稱"])):
            key = (f'{record["yr"]:03d}年{record["mn"]:02d}月', record["機構名稱"])
            if key in existing:
                continue
            writer.writerow(
                [
                    key[0],
                    record["機構名稱"],
                    record["使用者人數"],
                    record["代理收付金額_千元"],
                    record["移轉匯兌金額_千元"],
                    record["欄位說明"],
                    record["收受儲值金額_千元"],
                    record["儲值餘額_千元"],
                    record["代理收付餘額_千元"],
                    record["各類餘額合計_千元"],
                ]
            )
            existing.add(key)


def main() -> int:
    parser = argparse.ArgumentParser(description="更新金管會全業者統計資料")
    parser.add_argument("--dry-run", action="store_true", help="只檢查，不下載或寫入")
    args = parser.parse_args()

    if not DB_PATH.exists():
        parser.error(f"找不到資料庫：{DB_PATH}")

    links = disclosure_links(fetch_bytes(DISCLOSURE_URL))
    if not links:
        raise SystemExit("金管會頁面上找不到電子支付 ZIP 下載連結")

    existing = existing_periods()
    newest_existing = max(existing, default=(0, 0))
    missing = sorted(period for period in links if period > newest_existing)
    latest = max(links)
    print(f"金管會最新資料：{latest[0]}年{latest[1]:02d}月")
    if not missing:
        print("資料庫已是最新版本，無需更新。")
        return 0

    print("待匯入月份：" + "、".join(f"{y}年{m:02d}月" for y, m in missing))
    if args.dry_run:
        return 0

    all_records = []
    imported_periods: set[tuple[int, int]] = set()
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="fsc-disclosure-") as temp_dir:
        temp_path = Path(temp_dir)
        for period in missing:
            url = links[period]
            filename = unquote(Path(urlparse(url).path).name) or f"{period[0]}{period[1]:02d}.zip"
            zip_path = temp_path / filename
            print(f"下載：{period[0]}年{period[1]:02d}月")
            try:
                payload = fetch_bytes(url)
                if not zipfile.is_zipfile(io.BytesIO(payload)):
                    raise zipfile.BadZipFile("伺服器回應不是 ZIP 檔")
                zip_path.write_bytes(payload)
                records = parse_zip(zip_path)
                if not records:
                    raise ValueError("ZIP 內沒有可匯入資料")
                all_records.extend(records)
                imported_periods.add(period)
            except Exception as exc:
                message = f"{period[0]}年{period[1]:02d}月：{exc}"
                failures.append(message)
                print(f"警告：略過 {message}")

    if not all_records:
        raise SystemExit("下載完成，但沒有解析到任何資料")

    if latest in missing and latest not in imported_periods:
        raise SystemExit("最新月份下載或解析失敗，為避免發布舊資料而停止更新")

    inserted, replaced = import_to_db(all_records, DB_PATH)
    append_csv(all_records)
    print(f"完成：新增 {inserted} 筆，覆寫 {replaced} 筆，CSV 已同步。")
    if failures:
        print("未匯入的舊月份：" + "；".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
