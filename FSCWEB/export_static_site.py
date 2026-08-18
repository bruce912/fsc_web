#!/usr/bin/env python3
"""Export the Flask/SQLite application as a deployable static site."""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "static_site"
DB_PATH = BASE_DIR / "fsc_ebank.db"


def api_json(client, path):
    response = client.get(path)
    if response.status_code != 200:
        raise RuntimeError(f"{path}: HTTP {response.status_code}")
    return response.get_json()


def export_data(app_module):
    client = app_module.app.test_client()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    tables = api_json(client, "/api/tables")
    table_data = {}
    for table in tables:
        code = table["code"]
        columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{code}")')]
        rows = [dict(row) for row in conn.execute(f'SELECT * FROM "{code}"')]
        browse = api_json(client, f"/api/table/{code}/data?per_page=1")
        table_data[code] = {
            "columns": columns,
            "rows": rows,
            "browseColumns": browse["columns"],
            "browseLabels": browse["col_labels"],
            "numericColumns": api_json(client, f"/api/table/{code}/columns"),
            "structure": api_json(client, f"/api/table/{code}/structure"),
        }

    conn.close()
    docs_path = BASE_DIR / "資料庫欄位說明.md"
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dashboard": api_json(client, "/api/dashboard"),
        "tables": tables,
        "tableData": table_data,
        "docs": docs_path.read_text(encoding="utf-8") if docs_path.exists() else "# 找不到說明文件",
        "skipColumns": sorted(app_module.SKIP_COLS),
    }


def build_index():
    html = (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/', 'href="./static/')
    html = html.replace('src="/static/', 'src="./static/')
    bootstrap = '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>'
    html = html.replace(
        bootstrap,
        bootstrap + '\n<script src="./static/js/static-api.js"></script>',
        1,
    )
    return html


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"找不到資料庫：{DB_PATH}")

    try:
        import web_app
    except ModuleNotFoundError as exc:
        raise SystemExit("請先安裝網站相依套件：python3 -m pip install -r requirements.txt") from exc

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "data").mkdir(parents=True)
    shutil.copytree(BASE_DIR / "static", OUT_DIR / "static")
    shutil.copy2(BASE_DIR / "static_api.js", OUT_DIR / "static" / "js" / "static-api.js")
    (OUT_DIR / "index.html").write_text(build_index(), encoding="utf-8")
    payload = export_data(web_app)
    (OUT_DIR / "data" / "app-data.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    size_mb = (OUT_DIR / "data" / "app-data.json").stat().st_size / 1024 / 1024
    print(f"靜態網站已輸出：{OUT_DIR}")
    print(f"資料檔：data/app-data.json ({size_mb:.2f} MB)")
    print("本機預覽：python3 -m http.server 8001 --directory static_site")


if __name__ == "__main__":
    main()
