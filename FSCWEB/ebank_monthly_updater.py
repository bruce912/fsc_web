#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ebank_monthly_updater.py
========================
ebank.banking.gov.tw 月度資料自動更新 — 獨立執行版

使用方式：
  python ebank_monthly_updater.py                   # 一般執行
  python ebank_monthly_updater.py --reset           # 清除記錄，重新抓取所有月份
  python ebank_monthly_updater.py --months 6        # 首次執行抓最近 6 個月
  python ebank_monthly_updater.py --output ./data   # 指定 JSON 輸出目錄
  python ebank_monthly_updater.py --dry-run         # 僅預覽，不開啟瀏覽器

依賴安裝：
  pip install playwright
  playwright install chromium
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright, Frame, Page
except ImportError:
    print("請先安裝 Playwright：")
    print("   pip install playwright")
    print("   playwright install chromium")
    sys.exit(1)

# ════════════════════════════════════════════════════════════
# ⚙️  設定
# ════════════════════════════════════════════════════════════
BASE_URL           = "https://ebank.banking.gov.tw"
STATE_FILE         = Path(__file__).parent / ".ebank_updater_state.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent
FIRST_RUN_MONTHS   = 3
PAGE_LOAD_TIMEOUT  = 30.0   # 等待 DataTable 秒數
CLICK_SETTLE_SEC   = 1.2    # 點選選單後的穩定等待秒數
NAV_TIMEOUT_SEC    = 8      # 等待 targetframe 切換最長秒數
NAV_RETRY          = 2      # 導航失敗重試次數
FETCH_RETRY        = 2      # 資料抓取失敗重試次數

SUB_ITEMS = [
    {"name": "EC002W_儲值卡發行資料維護",                                               "base": "/EC/EC002W"},
    {"name": "EC011W_儲值卡類型資料維護",                                               "base": "/EC/EC011W"},
    {"name": "EP005B_電子支付帳戶戶數及使用者人數資料維護",                             "base": "/EP/EP005B"},
    {"name": "EP005W_電子支付帳戶使用者別交易資料維護",                                 "base": "/EP/EP005W"},
    {"name": "EP006B_電子支付機構業務帳戶別交易資訊應申報資料維護",                     "base": "/EP/EP006B"},
    {"name": "EP006W_電子支付機構業務業務別交易資訊應申報資料維護",                     "base": "/EP/EP006W"},
    {"name": "EP007W_電子支付帳戶支付工具別交易資料維護",                               "base": "/EP/EP007W"},
    {"name": "EP007X_儲值卡支付工具別交易資料維護",                                     "base": "/EP/EP007X"},
    {"name": "EP008W_電子支付機構特約機構交易資料維護",                                 "base": "/EP/EP008W"},
    {"name": "EP010W_電子支付機構實體通路支付服務交易資料維護",                         "base": "/EP/EP010W"},
    {"name": "EP010X_電子支付機構代理收付實質交易款項業務通路別交易資料維護",           "base": "/EP/EP010X"},
    {"name": "EP014W_電子支付機構收受使用者支付款項餘額資料維護",                       "base": "/EP/EP014W"},
    {"name": "EP015W_電子支付機構申訴案件統計情形資料維護",                             "base": "/EP/EP015W"},
    {"name": "EP105B_與境外機構合作或協助相關電子支付機構業務客戶數資料維護",           "base": "/EP/EP105B"},
    {"name": "EP105W_與境外機構合作或協助相關電子支付業務客戶資料維護",                 "base": "/EP/EP105W"},
    {"name": "EP106B_與境外機構合作或協助相關電子支付機構業務客戶交易資料維護",         "base": "/EP/EP106B"},
    {"name": "EP106W_與境外機構合作或協助相關電子支付機構業務業務別客戶交易資料維護",   "base": "/EP/EP106W"},
    {"name": "EP106X_與境外機構大陸地區合作或協助相關電子支付機構業務資料維護",         "base": "/EP/EP106X"},
    {"name": "EP107W_與境外機構合作或協助相關電子支付機構業務客戶帳戶支付工具資料維護", "base": "/EP/EP107W"},
    {"name": "EP108W_與境外機構合作或協助相關電子支付機構業務收款方客戶交易資料維護",   "base": "/EP/EP108W"},
    {"name": "EP108X_與境外機構合作或協助相關電子支付機構業務付款方客戶交易資料維護",   "base": "/EP/EP108X"},
    {"name": "EP114W_與境外機構合作或協助相關電子支付機構業務收受客戶支付款項餘額資料", "base": "/EP/EP114W"},
    {"name": "EP115W_與境外機構合作或協助相關電子支付機構業務申訴案件統計情形資料維護", "base": "/EP/EP115W"},
    {"name": "WB031W_電話申訴辦理情形資料維護",                                         "base": "/WB/WB031W"},
    {"name": "WB033W_人民陳情案件辦理情形資料維護",                                     "base": "/WB/WB033W"},
    {"name": "WB041W_行動支付業務資料維護",                                             "base": "/WB/WB041W"},
    {"name": "WB056W_電子支付機構端末設備共用情形資料維護",                              "base": "/WB/WB056W"},
]

# ════════════════════════════════════════════════════════════
# 📅  狀態管理
# ════════════════════════════════════════════════════════════

def load_state() -> Optional[dict]:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None

def save_state(yr: int, mn: int) -> None:
    STATE_FILE.write_text(
        json.dumps({"yr": yr, "mn": mn}, ensure_ascii=False),
        encoding="utf-8",
    )

def reset_state() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()

# ════════════════════════════════════════════════════════════
# 🛠️  工具函數
# ════════════════════════════════════════════════════════════

# ── yr / mn 容錯：不同表使用不同欄位名 ─────────────────────
_YR_KEYS = ("yr", "year", "Yr", "Year", "年度", "資料年度", "民國年")
_MN_KEYS = ("mn", "month", "Mn", "Month", "月", "月份", "資料月份")

def _to_int(v):
    try:
        if v is None:           return None
        if isinstance(v, bool): return None
        if isinstance(v, int):  return v
        s = str(v).strip()
        if not s: return None
        # 處理 "115 年 04 月" / "115/04" / "11504"
        import re as _re
        m = _re.search(r"(\d+)", s)
        return int(m.group(1)) if m else None
    except Exception:
        return None

def get_yr_mn(row: dict) -> Optional[dict]:
    """從 row 萃取 yr/mn，無法判斷時回 None。"""
    yr = mn = None
    for k in _YR_KEYS:
        if k in row:
            yr = _to_int(row[k])
            if yr is not None: break
    for k in _MN_KEYS:
        if k in row:
            mn = _to_int(row[k])
            if mn is not None: break

    # 若有 ym 欄位（如 "115/04"），補抓
    if (yr is None or mn is None):
        ym = row.get("ym") or row.get("Ym") or row.get("YM")
        if ym:
            import re as _re
            m = _re.match(r"\s*(\d+)\s*[/\-年]\s*(\d+)", str(ym))
            if m:
                if yr is None: yr = int(m.group(1))
                if mn is None: mn = int(m.group(2))

    if yr is None or mn is None:
        return None
    return {"yr": yr, "mn": mn}

def is_newer(row: dict, last: dict) -> bool:
    if not last:
        return True
    ym = get_yr_mn(row)
    if ym is None:
        # 無 yr/mn 的列：保守視為新資料
        return True
    return ym["yr"] > last["yr"] or (ym["yr"] == last["yr"] and ym["mn"] > last["mn"])

def max_yr_mn(rows: list) -> dict:
    result = {"yr": 0, "mn": 0}
    for r in rows:
        ym = get_yr_mn(r)
        if ym is None:
            continue
        if ym["yr"] > result["yr"] or (ym["yr"] == result["yr"] and ym["mn"] > result["mn"]):
            result = ym
    return result

def months_ago(yr_mn: dict, n: int) -> dict:
    yr, mn = yr_mn["yr"], yr_mn["mn"]
    mn -= n
    while mn <= 0:
        mn += 12
        yr -= 1
    return {"yr": yr, "mn": mn}

def build_detail_url(base: str, row: dict) -> str:
    ym = get_yr_mn(row)
    if ym:
        url = f"{BASE_URL}{base}/Edit?yr={ym['yr']}&mn={ym['mn']}"
    else:
        # 退而求其次：保留原 row 值
        url = f"{BASE_URL}{base}/Edit?yr={row.get('yr', '')}&mn={row.get('mn', '')}"
    sn = row.get("sn")
    if sn not in (None, ""):
        url += f"&sn={sn}"
    return url

def print_header():
    print("=" * 62)
    print("   ebank.banking.gov.tw  月度資料自動更新工具 v1.1")
    print("=" * 62)

# ════════════════════════════════════════════════════════════
# 🌐  Playwright 抓取邏輯
# ════════════════════════════════════════════════════════════

# 在 targetframe 執行：抓取 DataTable 所有分頁，回傳 rows 陣列
_JS_FETCH_ALL_ROWS = """
async () => {
    if (typeof $ === 'undefined' || !$('#dataTable').length)
        return { error: 'no_datatable', rows: [] };

    const table    = $('#dataTable').DataTable();
    const settings = table.settings()[0];

    // 取得 AJAX URL
    let ajaxUrl;
    if (typeof settings.ajax === 'string')       ajaxUrl = settings.ajax;
    else if (settings.ajax && settings.ajax.url) ajaxUrl = settings.ajax.url;
    else return { error: 'no_ajax_url', rows: [] };

    // 取得欄位定義（優先用 oAjaxData.columns，備用 aoColumns）
    let cols;
    if (settings.oAjaxData && settings.oAjaxData.columns) {
        cols = settings.oAjaxData.columns;
    } else if (settings.aoColumns) {
        cols = settings.aoColumns.map(c => ({ data: c.mData || c.data || '', name: c.sName || '' }));
    } else {
        return { error: 'no_columns', rows: [] };
    }

    const total    = settings.fnRecordsTotal ? settings.fnRecordsTotal() : 0;
    const pageSize = (settings._iDisplayLength > 0) ? settings._iDisplayLength : 25;
    const pages    = total > 0 ? Math.ceil(total / pageSize) : 1;

    function buildBody(start, page) {
        const p = new URLSearchParams();
        p.append('draw',          page);
        p.append('start',         start);
        p.append('length',        pageSize);
        p.append('search[value]', '');
        p.append('search[regex]', 'false');
        p.append('page',          page);
        cols.forEach((col, i) => {
            p.append(`columns[${i}][data]`,          col.data  || '');
            p.append(`columns[${i}][name]`,          col.name  || '');
            p.append(`columns[${i}][searchable]`,    col.searchable !== false);
            p.append(`columns[${i}][orderable]`,     col.orderable  !== false);
            p.append(`columns[${i}][search][value]`, '');
            p.append(`columns[${i}][search][regex]`, 'false');
        });
        return p.toString();
    }

    let allRows = [];
    for (let pg = 0; pg < pages; pg++) {
        const resp = await fetch(ajaxUrl, {
            method:      'POST',
            headers:     { 'Content-Type': 'application/x-www-form-urlencoded' },
            body:        buildBody(pg * pageSize, pg + 1),
            credentials: 'include',
        });
        if (!resp.ok) return { error: 'fetch_' + resp.status, rows: allRows };
        const json = await resp.json();
        if (json.data) allRows = allRows.concat(json.data);
    }

    // 去重（依 yr + mn + sn）
    const seen   = new Set();
    const unique = allRows.filter(row => {
        const key = `${row.yr}|${row.mn}|${row.sn ?? ''}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });

    return { rows: unique, total: unique.length };
}
"""

# 在 targetframe 執行：抓取明細頁面，回傳欄位物件
# 注意：
#   1) DOMParser 產生的文件不支援 innerText，需使用 textContent
#   2) 千分號 (例：56,968,388) 是同一筆數字，需移除逗號
#   3) 表格可能含 rowspan/colspan 階層結構（如 EP014W：
#      電子支付帳戶 > 代理收付款項餘額 > 代理收付款項餘額(不含...) → 值
#      重複子標籤在不同階層出現，需用階層 key 區分）
#   4) 計算欄位（如「小計」、「總計」）為純文字而非 input
_JS_FETCH_DETAIL = """
async (url) => {
    const resp = await fetch(url, { credentials: 'include' });
    if (!resp.ok) return { _error: 'HTTP ' + resp.status };
    const html = await resp.text();
    const doc  = new DOMParser().parseFromString(html, 'text/html');
    const data = {};

    // ── Helpers ──
    const normVal = (v) => {
        if (v == null) return v;
        let s = String(v).trim();
        if (/^-?\\d{1,3}(,\\d{3})+(\\.\\d+)?$/.test(s)) s = s.replace(/,/g, '');
        return s;
    };
    const INPUT_SEL    = 'input[type="text"],input[type="number"],input[type="tel"],input:not([type]),textarea,select';
    const cellText     = (cell) => (cell.textContent || '').replace(/\\s+/g, ' ').trim();
    const isNumeric    = (s) => /\\d/.test(s) && /^-?[\\d,]+(\\.\\d+)?$/.test(s);
    const cellHasInput = (cell) => !!cell.querySelector(INPUT_SEL);
    const set = (key, value) => {
        if (!key) return;
        if (!(key in data)) data[key] = normVal(value);
    };

    // 1) 所有具名 input/textarea/select → 用 name/id/placeholder 收
    doc.querySelectorAll(INPUT_SEL).forEach(inp => {
        const key = inp.name || inp.id || inp.placeholder;
        if (!key || inp.type === 'hidden') return;
        set(key, (inp.value || '').trim());
    });

    // 2) checkbox / radio (已勾選)
    doc.querySelectorAll('input[type="checkbox"],input[type="radio"]').forEach(inp => {
        if (!inp.checked) return;
        const key = inp.name || inp.id;
        if (!key) return;
        const v = (inp.value || '').trim();
        if (inp.type === 'radio') {
            set(key, v);
        } else {
            if (Array.isArray(data[key])) data[key].push(normVal(v));
            else if (key in data)         data[key] = [data[key], normVal(v)];
            else                          data[key] = normVal(v);
        }
    });

    // 3) 表格 — 建 virtual grid 展開 rowspan/colspan，再做階層 label→value
    doc.querySelectorAll('table').forEach(table => {
        const trList = Array.from(table.rows || []);
        if (!trList.length) return;

        // 3a) 展開為虛擬網格 grid[r][c] = cell
        const grid = [];
        for (let r = 0; r < trList.length; r++) {
            if (!grid[r]) grid[r] = [];
            let c = 0;
            const cells = Array.from(trList[r].cells || []);
            for (const cell of cells) {
                while (grid[r][c]) c++;
                const rs = parseInt(cell.getAttribute('rowspan') || '1', 10) || 1;
                const cs = parseInt(cell.getAttribute('colspan') || '1', 10) || 1;
                for (let dr = 0; dr < rs; dr++) {
                    if (!grid[r + dr]) grid[r + dr] = [];
                    for (let dc = 0; dc < cs; dc++) {
                        grid[r + dr][c + dc] = cell;
                    }
                }
                c += cs;
            }
        }

        // 3b) 偵測「資料表」header：用 grid[0] (已展開 colspan) 而非原始 cells
        //     並要求 header 含 >=2 種不同文字 — 避免 <th colspan=N>某區塊標題</th>
        //     被誤判 (如「維護人基本資料」這種 section header)
        const headerRow = grid[0] || [];
        const headerTexts = headerRow.map(c => c ? cellText(c) : '');
        const distinctHeaders = new Set(headerTexts.filter(Boolean));
        const allTh = headerRow.length >= 2 &&
                      distinctHeaders.size >= 2 &&
                      headerRow.every(c => c && c.tagName === 'TH') &&
                      headerRow.every(c => !(parseInt(c.getAttribute('rowspan')||'1',10) > 1));
        const headers = allTh ? headerTexts : null;

        // 3c) 對每個虛擬列做 left-to-right 階層配對
        for (let r = 0; r < grid.length; r++) {
            const row = grid[r] || [];
            const labelStack = [];
            const seen = new Set();

            // rowLabel: 此列第一個「文字標籤 cell」(非 input、非數字)
            // 用於「垂直軸資料表」(EC002W) 產生「列標籤/欄標籤」key
            let rowLabel = null;
            if (headers && r > 0) {
                for (let cc = 0; cc < row.length; cc++) {
                    const ce = row[cc];
                    if (!ce) continue;
                    if (cellHasInput(ce)) break;
                    const t = cellText(ce);
                    if (!t) continue;
                    if (isNumeric(t)) break;
                    rowLabel = t;
                    break;
                }
            }

            // 是否能安全用 rowLabel/colHeader 命名：階層不深 (labelStack 至多含 rowLabel)
            const canUseRowLabel = () => {
                if (!rowLabel || !headers) return false;
                if (labelStack.length === 0) return true;
                if (labelStack.length === 1 && labelStack[0] === rowLabel) return true;
                return false;
            };

            for (let c = 0; c < row.length; c++) {
                const cell = row[c];
                if (!cell || seen.has(cell)) continue;
                seen.add(cell);

                if (cellHasInput(cell)) {
                    const inp = cell.querySelector(INPUT_SEL);
                    const value = (inp.value || '').trim();
                    if (labelStack.length) {
                        set(labelStack.join(' / '), value);              // 完整階層 key
                        set(labelStack[labelStack.length - 1], value);   // 末層短 key
                    }
                    if (headers && r > 0 && headers[c]) {
                        set('[' + (r - 1) + '].' + headers[c], value);   // [rowIdx].header
                        if (canUseRowLabel()) {
                            set(rowLabel + ' / ' + headers[c], value);   // 列標/欄標
                        }
                    }
                    labelStack.length = 0;
                    continue;
                }

                const txt = cellText(cell);
                if (!txt) continue;

                if (isNumeric(txt)) {
                    if (labelStack.length) {
                        set(labelStack.join(' / '), txt);
                        set(labelStack[labelStack.length - 1], txt);
                    }
                    if (headers && r > 0 && headers[c]) {
                        set('[' + (r - 1) + '].' + headers[c], txt);
                        if (canUseRowLabel()) {
                            set(rowLabel + ' / ' + headers[c], txt);
                        }
                    }
                    labelStack.length = 0;
                } else {
                    if (headers && r > 0 && headers[c]) {
                        set('[' + (r - 1) + '].' + headers[c], txt);
                    }
                    labelStack.push(txt);
                }
            }
        }
    });

    // 4) 2-cell 屬性配對 backup pass (catch property tables like 維護人基本資料)
    //    任何 2-cell 列：cells[0]=label, cells[1]=value (含純文字值)
    doc.querySelectorAll('tr').forEach(tr => {
        const cells = Array.from(tr.cells || []);
        if (cells.length !== 2) return;
        if (cellHasInput(cells[0])) return;
        const label = cellText(cells[0]);
        if (!label || isNumeric(label)) return;
        const valCell = cells[1];
        const inp = valCell.querySelector(INPUT_SEL);
        const value = inp ? (inp.value || '').trim() : cellText(valCell);
        if (value) set(label, value);
    });

    // 5) <dl><dt><dd>
    doc.querySelectorAll('dl').forEach(dl => {
        dl.querySelectorAll('dt').forEach(dt => {
            const dd = dt.nextElementSibling;
            if (!dd || dd.tagName !== 'DD') return;
            const label = cellText(dt);
            if (!label) return;
            const inp = dd.querySelector(INPUT_SEL);
            const value = inp ? (inp.value || '').trim() : cellText(dd);
            set(label, value);
        });
    });

    return data;
}
"""

# ── 等待 targetframe DataTable 就緒 ────────────────────────
async def wait_for_datatable(target_frame: Frame, timeout_sec: float) -> bool:
    await asyncio.sleep(CLICK_SETTLE_SEC)
    loop     = asyncio.get_running_loop()
    deadline = loop.time() + timeout_sec
    while loop.time() < deadline:
        try:
            ready = await target_frame.evaluate("""
                () => {
                    try {
                        if (typeof $ === 'undefined') return false;
                        if (!$('#dataTable').length)  return false;
                        const s = $('#dataTable').DataTable().settings()[0];
                        const hasAjax = !!(s.ajax || (s.oAjaxData && s.oAjaxData.columns));
                        return hasAjax && typeof s.fnRecordsTotal === 'function';
                    } catch(e) { return false; }
                }
            """)
            if ready:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.4)
    return False

# ── 點選左側選單，等待 targetframe 切換到目標 URL ──────────
async def navigate_to(page: Page, menu_frame: Frame, base: str) -> bool:
    target_url = BASE_URL + base
    loop = asyncio.get_running_loop()

    for attempt in range(NAV_RETRY + 1):
        clicked = await menu_frame.evaluate(f"""
            () => {{
                const link = $('a').filter(function() {{
                    return this.href === '{target_url}';
                }})[0];
                if (link) {{ link.click(); return true; }}
                return false;
            }}
        """)
        if not clicked:
            return False

        deadline = loop.time() + NAV_TIMEOUT_SEC
        while loop.time() < deadline:
            try:
                href = await page.evaluate("""
                    () => {
                        try { return window.frames['targetframe'].location.href; }
                        catch(e) { return ''; }
                    }
                """)
                if href == target_url:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.2)

        # 未在時限內切換，重試
        if attempt < NAV_RETRY:
            await asyncio.sleep(0.5)

    return False

# ── 抓取所有列表列（含重試）────────────────────────────────
async def fetch_rows(target_frame: Frame) -> dict:
    last_err = None
    for _ in range(FETCH_RETRY + 1):
        try:
            result = await target_frame.evaluate(_JS_FETCH_ALL_ROWS)
            if not result.get("error"):
                return result
            last_err = result["error"]
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(0.5)
    return {"error": last_err, "rows": []}

# ── 找 frame：name attribute → iframe id/name attribute → URL 子字串 ─
async def find_frame_async(page: Page, key: str) -> Optional[Frame]:
    """非同步版本：name → id (element attr) → URL → JS window.frames"""
    fr = page.frame(name=key)
    if fr:
        return fr

    # 用 iframe 的 id / name attribute 反查 (await 版)
    for f in list(page.frames):
        try:
            el = await f.frame_element()
            attr_id   = (await el.get_attribute("id")) or ""
            attr_name = (await el.get_attribute("name")) or ""
            if attr_id == key or attr_name == key:
                return f
        except Exception:
            continue

    # URL 子字串
    key_lower = key.lower()
    for f in list(page.frames):
        if key_lower in (f.url or "").lower():
            return f

    return None

# ── 等待使用者在登入頁完成登入 ─────────────────────────────
async def wait_for_login(page: Page) -> bool:
    loop = asyncio.get_running_loop()

    print("\n" + "=" * 62)
    print("  請在瀏覽器視窗中輸入帳號/密碼並完成登入驗證。")
    print("  登入成功後（畫面已看到左側選單），")
    print("  回到此終端機視窗按 Enter 繼續。")
    print("=" * 62)

    await loop.run_in_executor(None, input, "\n  ▶ 登入完成後，按 Enter 繼續... ")

    # 不強制 goto /Frame — 先確認使用者目前頁面是否已具備 frames
    print("\n  檢查系統主畫面 frame ...")

    async def has_both_frames() -> bool:
        mf = await find_frame_async(page, "menuframe")
        tf = await find_frame_async(page, "targetframe")
        return mf is not None and tf is not None

    if await has_both_frames():
        return True

    # 沒抓到 → 嘗試導航到 /Frame
    print(f"  目前頁面：{page.url}")
    print(f"  未偵測到 menuframe / targetframe，嘗試導航到 {BASE_URL}/Frame ...")
    try:
        await page.goto(f"{BASE_URL}/Frame", wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        print(f"  (頁面載入提示: {e})")

    for _ in range(30):
        if await has_both_frames():
            return True
        await asyncio.sleep(0.5)

    # 最後一次：印出所有 frame 資訊以利除錯
    print("\n  [診斷] 目前 page.url =", page.url)
    print("  [診斷] 所有 frame：")
    for idx, f in enumerate(page.frames):
        try:
            el = await f.frame_element()
            attr_id   = await el.get_attribute("id")   if el else None
            attr_name = await el.get_attribute("name") if el else None
        except Exception:
            attr_id, attr_name = None, None
        print(f"    [{idx}] name={f.name!r}  id_attr={attr_id!r}  name_attr={attr_name!r}")
        print(f"         url={f.url}")

    return False

# ════════════════════════════════════════════════════════════
# 🚀  主流程
# ════════════════════════════════════════════════════════════

async def run(args):
    print_header()

    if args.reset:
        reset_state()
        print("\n已清除上次執行記錄，將重新抓取所有月份\n")

    first_run_months = args.months
    state            = load_state()
    is_first_run     = state is None

    if is_first_run:
        print(f"\n首次執行：將抓取最近 {first_run_months} 個月資料")
    else:
        print(f"\n上次更新：民國 {state['yr']} 年 {state['mn']:02d} 月")
        print("   只會下載此日期之後的新記錄")

    if args.dry_run:
        print(f"\n[Dry-run] 共 {len(SUB_ITEMS)} 個項目，不實際執行。")
        for i, item in enumerate(SUB_ITEMS):
            print(f"  [{i+1:2d}] {item['name']}")
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(ignore_https_errors=True)
        page    = await context.new_page()

        print(f"\n開啟瀏覽器，前往 {BASE_URL} ...")
        try:
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
        except Exception as e:
            print(f"   (頁面載入提示: {e}，繼續等待登入)")

        logged_in = await wait_for_login(page)
        if not logged_in:
            print("\n偵測不到系統主畫面（menuframe/targetframe），請確認已正確登入後重試")
            await browser.close()
            return

        print("\n登入確認，開始資料擷取\n")
        print("-" * 62)

        menu_frame = await find_frame_async(page, "menuframe")
        if not menu_frame:
            print("找不到 menuframe，請確認頁面為 /Frame")
            print(f"目前 page.url = {page.url}")
            print("所有 frame:")
            for idx, f in enumerate(page.frames):
                print(f"  [{idx}] name={f.name!r} url={f.url}")
            await browser.close()
            return

        results    = {}
        global_max = {"yr": 0, "mn": 0}
        total_new  = 0
        err_count  = 0

        for i, item in enumerate(SUB_ITEMS):
            code  = item["name"].split("_")[0]
            label = f"[{i+1:2d}/{len(SUB_ITEMS)}] {code}"
            print(f"{label:<40}", end="", flush=True)

            # 1. 導航到子項目
            try:
                nav_ok = await navigate_to(page, menu_frame, item["base"])
            except Exception:
                nav_ok = False

            if not nav_ok:
                print("找不到選單連結，跳過")
                err_count += 1
                results[item["name"]] = {"skipped": True, "reason": "menu_link_not_found", "details": []}
                continue

            # 2. 取得 targetframe
            target_frame = await find_frame_async(page, "targetframe")
            if not target_frame:
                print("找不到 targetframe，跳過")
                err_count += 1
                results[item["name"]] = {"skipped": True, "reason": "no_targetframe", "details": []}
                continue

            # 3. 等待 DataTable 就緒
            ready = await wait_for_datatable(target_frame, PAGE_LOAD_TIMEOUT)
            if not ready:
                print("DataTable 載入逾時，跳過")
                err_count += 1
                results[item["name"]] = {"skipped": True, "reason": "datatable_timeout", "details": []}
                continue

            # 4. 抓取所有列表列
            fetched = await fetch_rows(target_frame)
            if fetched.get("error"):
                print(f"抓取失敗: {fetched['error']}，跳過")
                err_count += 1
                results[item["name"]] = {"skipped": True, "reason": fetched["error"], "details": []}
                continue

            rows = fetched.get("rows", [])
            if not rows:
                print("— 無資料")
                results[item["name"]] = {"totalRows": 0, "newRows": 0, "details": []}
                continue

            # 5. 過濾新年月（容錯：沒 yr/mn 的列直接全收）
            has_yr_mn = any(get_yr_mn(r) is not None for r in rows)

            if not has_yr_mn:
                print("(無年月欄位，全部抓取) ", end="", flush=True)
                target_rows = rows
            elif is_first_run:
                latest      = max_yr_mn(rows)
                cutoff      = months_ago(latest, first_run_months)
                def _keep_first_run(r):
                    ym = get_yr_mn(r)
                    if ym is None:
                        return True  # 無年月者保留
                    return ym["yr"] > cutoff["yr"] or \
                           (ym["yr"] == cutoff["yr"] and ym["mn"] >= cutoff["mn"])
                target_rows = [r for r in rows if _keep_first_run(r)]
            else:
                target_rows = [r for r in rows if is_newer(r, state)]

            if not target_rows:
                print("— 無新資料")
                results[item["name"]] = {"totalRows": fetched["total"], "newRows": 0, "details": []}
                continue

            # 6. 逐筆抓取明細頁面
            details = []
            for row in target_rows:
                url = build_detail_url(item["base"], row)
                try:
                    detail = await target_frame.evaluate(_JS_FETCH_DETAIL, url)
                    details.append({**row, **detail})
                except Exception as e:
                    details.append({**row, "_fetchError": str(e)})

            # 7. 更新全局最大年月
            item_max = max_yr_mn(target_rows)
            if (item_max["yr"] > global_max["yr"] or
                    (item_max["yr"] == global_max["yr"] and item_max["mn"] > global_max["mn"])):
                global_max = item_max

            total_new += len(details)
            print(f"新增 {len(details)} 筆")
            results[item["name"]] = {
                "totalRows": fetched["total"],
                "newRows":   len(details),
                "details":   details,
            }

        await browser.close()

    print("-" * 62)
    print(f"   處理完成：{len(SUB_ITEMS)} 個項目，新增 {total_new} 筆，錯誤 {err_count} 項")
    print("-" * 62)

    if total_new == 0:
        print("\n所有項目均無新資料，未產生輸出檔案")
        return

    # 儲存狀態
    if global_max["yr"] > 0:
        save_state(global_max["yr"], global_max["mn"])
        print(f"\n已記錄最新年月：民國 {global_max['yr']} 年 {global_max['mn']:02d} 月")
        print(f"   （狀態檔：{STATE_FILE}）")

    # 輸出 JSON
    yr_str   = str(global_max["yr"])
    mn_str   = str(global_max["mn"]).zfill(2)
    filename = f"ebank_update_{yr_str}_{mn_str}.json"
    out_path = output_dir / filename

    payload = {
        "scriptVersion":   "1.1",
        "extractedAt":     datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "latestYrMn":      global_max,
        "totalNewRecords": total_new,
        "isFirstRun":      is_first_run,
        "data":            results,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n已儲存：{out_path.resolve()}")
    print(f"   共 {total_new} 筆新記錄")
    print(f"\n完成！")


# ════════════════════════════════════════════════════════════
# ▶  入口點
# ════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="ebank.banking.gov.tw 月度資料自動更新工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  python ebank_monthly_updater.py
  python ebank_monthly_updater.py --reset
  python ebank_monthly_updater.py --months 6
  python ebank_monthly_updater.py --output /Users/me/Downloads
  python ebank_monthly_updater.py --dry-run
        """
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="清除上次記錄，重新從頭抓取所有月份"
    )
    parser.add_argument(
        "--months", type=int, default=FIRST_RUN_MONTHS, metavar="N",
        help=f"首次執行往前抓幾個月（預設 {FIRST_RUN_MONTHS}）"
    )
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT_DIR), metavar="DIR",
        help=f"JSON 輸出目錄（預設：{DEFAULT_OUTPUT_DIR}）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只列出將處理的項目，不開啟瀏覽器執行"
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
