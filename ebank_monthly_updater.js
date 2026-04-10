/**
 * ╔══════════════════════════════════════════════════════════════╗
 * ║         ebank.banking.gov.tw  月度資料自動更新腳本           ║
 * ║                  版本：1.0  (2026-03)                        ║
 * ╠══════════════════════════════════════════════════════════════╣
 * ║  使用方法（Chrome DevTools Snippet）：                       ║
 * ║  1. 登入 https://ebank.banking.gov.tw/Frame                 ║
 * ║  2. 按 F12 → Sources → Snippets → 新增 Snippet              ║
 * ║  3. 貼上此腳本，按 Ctrl+Enter 執行                          ║
 * ║                                                              ║
 * ║  首次執行：下載最近 3 個月資料                               ║
 * ║  後續執行：只下載上次記錄後的新資料                          ║
 * ║                                                              ║
 * ║  重設（重新全抓）：                                          ║
 * ║    在 Console 執行：                                         ║
 * ║    localStorage.removeItem('ebank_last_update')             ║
 * ║    然後重新執行此腳本                                         ║
 * ╚══════════════════════════════════════════════════════════════╝
 */

(async function ebankMonthlyUpdater() {
  'use strict';

  // ═══════════════════════════════════════════════════════════════
  // ⚙️  設定區（可依需求調整）
  // ═══════════════════════════════════════════════════════════════
  const CONFIG = {
    // 首次執行時，往前抓幾個月（設 0 只抓最新月）
    FIRST_RUN_MONTHS: 3,

    // 等待頁面 DataTable 載入的最長秒數
    PAGE_LOAD_TIMEOUT_SEC: 30,

    // 點選選單後的初始等待毫秒（避免 DataTable 誤判為前頁）
    CLICK_SETTLE_MS: 1200,

    // localStorage key（用來記憶上次抓取的年月）
    STORAGE_KEY: 'ebank_last_update',
  };

  // ═══════════════════════════════════════════════════════════════
  // 📋  27 個子項目清單
  // ═══════════════════════════════════════════════════════════════
  const SUB_ITEMS = [
    { name: 'EC002W_儲值卡發行資料維護',                                                  base: '/EC/EC002W' },
    { name: 'EC011W_儲值卡類型資料維護',                                                  base: '/EC/EC011W' },
    { name: 'EP005B_電子支付帳戶戶數及使用者人數資料維護',                                base: '/EP/EP005B' },
    { name: 'EP005W_電子支付帳戶使用者別交易資料維護',                                    base: '/EP/EP005W' },
    { name: 'EP006B_電子支付機構業務帳戶別交易資訊應申報資料維護',                        base: '/EP/EP006B' },
    { name: 'EP006W_電子支付機構業務業務別交易資訊應申報資料維護',                        base: '/EP/EP006W' },
    { name: 'EP007W_電子支付帳戶支付工具別交易資料維護',                                  base: '/EP/EP007W' },
    { name: 'EP007X_儲值卡支付工具別交易資料維護',                                        base: '/EP/EP007X' },
    { name: 'EP008W_電子支付機構特約機構交易資料維護',                                    base: '/EP/EP008W' },
    { name: 'EP010W_電子支付機構實體通路支付服務交易資料維護',                            base: '/EP/EP010W' },
    { name: 'EP010X_電子支付機構代理收付實質交易款項業務通路別交易資料維護',              base: '/EP/EP010X' },
    { name: 'EP014W_電子支付機構收受使用者支付款項餘額資料維護',                          base: '/EP/EP014W' },
    { name: 'EP015W_電子支付機構申訴案件統計情形資料維護',                                base: '/EP/EP015W' },
    { name: 'EP105B_與境外機構合作或協助相關電子支付機構業務客戶數資料維護',              base: '/EP/EP105B' },
    { name: 'EP105W_與境外機構合作或協助相關電子支付業務客戶資料維護',                    base: '/EP/EP105W' },
    { name: 'EP106B_與境外機構合作或協助相關電子支付機構業務客戶交易資料維護',            base: '/EP/EP106B' },
    { name: 'EP106W_與境外機構合作或協助相關電子支付機構業務業務別客戶交易資料維護',      base: '/EP/EP106W' },
    { name: 'EP106X_與境外機構大陸地區合作或協助相關電子支付機構業務資料維護',            base: '/EP/EP106X' },
    { name: 'EP107W_與境外機構合作或協助相關電子支付機構業務客戶帳戶支付工具資料維護',    base: '/EP/EP107W' },
    { name: 'EP108W_與境外機構合作或協助相關電子支付機構業務收款方客戶交易資料維護',      base: '/EP/EP108W' },
    { name: 'EP108X_與境外機構合作或協助相關電子支付機構業務付款方客戶交易資料維護',      base: '/EP/EP108X' },
    { name: 'EP114W_與境外機構合作或協助相關電子支付機構業務收受客戶支付款項餘額資料',   base: '/EP/EP114W' },
    { name: 'EP115W_與境外機構合作或協助相關電子支付機構業務申訴案件統計情形資料維護',    base: '/EP/EP115W' },
    { name: 'WB031W_電話申訴辦理情形資料維護',                                            base: '/WB/WB031W' },
    { name: 'WB033W_人民陳情案件辦理情形資料維護',                                        base: '/WB/WB033W' },
    { name: 'WB041W_行動支付業務資料維護',                                                base: '/WB/WB041W' },
    { name: 'WB056W_電子支付機構端末設備共用情形資料維護',                                base: '/WB/WB056W' },
  ];

  // ═══════════════════════════════════════════════════════════════
  // 🖥️  進度面板 UI
  // ═══════════════════════════════════════════════════════════════
  const UI = (() => {
    // 移除已存在的舊面板
    const existing = document.getElementById('ebank-updater-panel');
    if (existing) existing.remove();

    const panel = document.createElement('div');
    panel.id = 'ebank-updater-panel';
    panel.style.cssText = [
      'position:fixed', 'top:20px', 'right:20px', 'z-index:2147483647',
      'background:#0f172a', 'color:#e2e8f0', 'border-radius:14px',
      'padding:20px 22px', 'width:400px', 'font-family:ui-monospace,monospace',
      'font-size:13px', 'box-shadow:0 12px 48px rgba(0,0,0,0.6)',
      'border:1px solid #1e293b', 'line-height:1.6',
    ].join(';');

    panel.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <span style="font-size:15px;font-weight:700;color:#7dd3fc">
          📊 ebank 月度資料更新
        </span>
        <span id="ebu-close" style="cursor:pointer;color:#64748b;font-size:18px;line-height:1"
              title="關閉">✕</span>
      </div>
      <div id="ebu-status" style="color:#94a3b8;margin-bottom:10px;min-height:20px">
        初始化...
      </div>
      <div style="background:#1e293b;border-radius:6px;height:8px;margin-bottom:14px;overflow:hidden">
        <div id="ebu-bar" style="height:100%;width:0%;
             background:linear-gradient(90deg,#38bdf8,#34d399);
             transition:width 0.4s ease;border-radius:6px"></div>
      </div>
      <div style="display:flex;gap:16px;margin-bottom:12px;font-size:12px;color:#64748b">
        <span>項目 <b id="ebu-count" style="color:#94a3b8">0 / ${SUB_ITEMS.length}</b></span>
        <span>新增筆數 <b id="ebu-new" style="color:#34d399">0</b></span>
        <span>略過 <b id="ebu-skip" style="color:#64748b">0</b></span>
        <span>錯誤 <b id="ebu-err" style="color:#f87171">0</b></span>
      </div>
      <div id="ebu-log" style="
        max-height:180px;overflow-y:auto;font-size:11px;
        border-top:1px solid #1e293b;padding-top:10px;
        scrollbar-width:thin;scrollbar-color:#334155 transparent
      "></div>
    `;
    document.body.appendChild(panel);

    document.getElementById('ebu-close').onclick = () => panel.remove();

    let newCount = 0, skipCount = 0, errCount = 0;

    return {
      status(msg, color = '#94a3b8') {
        const el = document.getElementById('ebu-status');
        el.style.color = color;
        el.textContent = msg;
      },
      progress(idx) {
        const pct = Math.round((idx / SUB_ITEMS.length) * 100);
        document.getElementById('ebu-bar').style.width = pct + '%';
        document.getElementById('ebu-count').textContent = `${idx} / ${SUB_ITEMS.length}`;
      },
      addNew(n) {
        newCount += n;
        document.getElementById('ebu-new').textContent = newCount;
      },
      addSkip() {
        skipCount++;
        document.getElementById('ebu-skip').textContent = skipCount;
      },
      addErr() {
        errCount++;
        document.getElementById('ebu-err').textContent = errCount;
      },
      log(msg, color = '#64748b') {
        const d = document.getElementById('ebu-log');
        const line = document.createElement('div');
        line.style.color = color;
        line.textContent = msg;
        d.appendChild(line);
        d.scrollTop = d.scrollHeight;
      },
      done(msg) {
        this.status(msg, '#34d399');
        document.getElementById('ebu-bar').style.width = '100%';
        document.getElementById('ebu-bar').style.background = '#34d399';
        this.log('─'.repeat(44), '#1e293b');
        this.log('✅ 完成！面板將於 8 秒後自動關閉', '#34d399');
        setTimeout(() => panel && panel.remove(), 8000);
      },
      fail(msg) {
        this.status(msg, '#f87171');
        document.getElementById('ebu-bar').style.background = '#f87171';
      },
      getNewCount() { return newCount; },
    };
  })();

  // ═══════════════════════════════════════════════════════════════
  // 🛠️  工具函數
  // ═══════════════════════════════════════════════════════════════

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  /**
   * 點選左側選單並等待 targetframe URL 切換到目標頁面
   */
  async function navigateTo(base) {
    const targetUrl = 'https://ebank.banking.gov.tw' + base;
    const mf = window.frames['menuframe'];
    if (!mf || !mf.$) return false;

    const link = mf.$('a').filter(function () { return this.href === targetUrl; })[0];
    if (!link) return false;
    link.click();

    // 等待 targetframe 導航到目標 URL
    const deadline = Date.now() + 8000;
    while (Date.now() < deadline) {
      try {
        if (window.frames['targetframe'].location.href === targetUrl) break;
      } catch (e) { /* cross-origin 暫時錯誤，繼續等 */ }
      await sleep(200);
    }
    return true;
  }

  /**
   * 等待 DataTable 完成初始化（含資料載入）
   */
  async function waitForDataTable(timeoutSec) {
    // 先讓頁面穩定一下，避免讀到舊頁面的 DataTable
    await sleep(CONFIG.CLICK_SETTLE_MS);

    const deadline = Date.now() + timeoutSec * 1000;
    while (Date.now() < deadline) {
      try {
        const tf = window.frames['targetframe'];
        if (tf && tf.$ && tf.$('#dataTable').length) {
          const s = tf.$('#dataTable').DataTable().settings()[0];
          if (s.oAjaxData && s.oAjaxData.columns && typeof s.fnRecordsTotal === 'function') {
            return true;
          }
        }
      } catch (e) { /* 頁面尚未就緒 */ }
      await sleep(400);
    }
    return false;
  }

  /**
   * 抓取當前 DataTable 的所有分頁資料（同步 XHR）
   * 回傳 { rows, total, base, error }
   */
  function fetchAllRows() {
    const tf = window.frames['targetframe'];
    const $ = tf.$;
    if (!$ || !$('#dataTable').length) return { error: 'no_datatable', rows: [] };

    const table = $('#dataTable').DataTable();
    const settings = table.settings()[0];
    if (!settings.oAjaxData) return { error: 'no_ajax_data', rows: [] };

    let ajaxUrl;
    if (typeof settings.ajax === 'string')           ajaxUrl = settings.ajax;
    else if (settings.ajax && settings.ajax.url)     ajaxUrl = settings.ajax.url;
    else                                             return { error: 'no_ajax_url', rows: [] };

    const cols     = settings.oAjaxData.columns;
    const total    = settings.fnRecordsTotal ? settings.fnRecordsTotal() : 0;
    const pageSize = settings._iDisplayLength || 12;
    const pages    = Math.ceil(total / pageSize) || 1;

    function buildParams(start, page) {
      const p = {
        draw: page, start, length: pageSize,
        'search[value]': '', 'search[regex]': false, page,
      };
      cols.forEach((col, i) => {
        p[`columns[${i}][data]`]           = col.data;
        p[`columns[${i}][name]`]           = col.name || '';
        p[`columns[${i}][searchable]`]     = col.searchable !== false;
        p[`columns[${i}][orderable]`]      = col.orderable !== false;
        p[`columns[${i}][search][value]`]  = '';
        p[`columns[${i}][search][regex]`]  = false;
      });
      return p;
    }

    let allRows = [];
    for (let pg = 0; pg < pages; pg++) {
      let result = null;
      $.ajax({
        url: ajaxUrl, type: 'POST',
        data: buildParams(pg * pageSize, pg + 1),
        async: false,
        success: r => { result = r; },
      });
      if (result && result.data) allRows = allRows.concat(result.data);
    }

    // 去重複（依 yr + mn + sn）
    const seen = new Set();
    const unique = allRows.filter(row => {
      const key = `${row.yr}|${row.mn}|${row.sn ?? ''}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    return { rows: unique, total: unique.length, base: ajaxUrl.replace('/IndexQuery', '') };
  }

  /**
   * 抓取單筆明細頁面（同步 XHR），回傳欄位物件
   */
  function fetchDetail(editUrl) {
    const tf  = window.frames['targetframe'];
    const xhr = new tf.XMLHttpRequest();
    xhr.open('GET', editUrl, false);
    xhr.withCredentials = true;
    xhr.send();
    if (xhr.status !== 200) return { _error: 'HTTP ' + xhr.status };

    const doc  = new DOMParser().parseFromString(xhr.responseText, 'text/html');
    const data = {};

    // 抓 input / textarea / select
    doc.querySelectorAll('input[type="text"],input[type="number"],textarea,select').forEach(inp => {
      const key = inp.name || inp.id || inp.placeholder;
      if (key && inp.type !== 'hidden') data[key] = (inp.value || '').trim();
    });

    // 抓 table 中的 label–value 配對
    doc.querySelectorAll('table tr').forEach(row => {
      const cells = row.querySelectorAll('td,th');
      if (cells.length < 2) return;
      const label = (cells[0].innerText || '').trim();
      if (!label) return;
      const inp   = cells[1].querySelector(
        'input[type="text"],input:not([type="hidden"]),textarea,select'
      );
      const value = inp
        ? (inp.value || '').trim()
        : (cells[1].innerText || '').trim();
      if (label) data[label] = value;
    });

    return data;
  }

  /**
   * 觸發瀏覽器下載 JSON 檔案
   */
  function downloadJSON(filename, payload) {
    const blob = new Blob(
      [JSON.stringify(payload, null, 2)],
      { type: 'application/json;charset=utf-8' }
    );
    const url = URL.createObjectURL(blob);
    const a   = Object.assign(document.createElement('a'), { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  }

  // ═══════════════════════════════════════════════════════════════
  // 📅  上次更新記錄（localStorage）
  // ═══════════════════════════════════════════════════════════════

  function getLastUpdate() {
    try {
      const v = localStorage.getItem(CONFIG.STORAGE_KEY);
      return v ? JSON.parse(v) : null;
    } catch (e) { return null; }
  }

  function saveLastUpdate(yr, mn) {
    try {
      localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify({ yr, mn }));
    } catch (e) { /* 忽略 */ }
  }

  /** 民國年月比大小：row 是否比 last 新 */
  function isNewer(row, last) {
    if (!last) return true;
    return row.yr > last.yr || (row.yr === last.yr && row.mn > last.mn);
  }

  /** 從 rows 中找出最大年月 */
  function maxYrMn(rows) {
    return rows.reduce((m, r) => {
      if (r.yr > m.yr || (r.yr === m.yr && r.mn > m.mn)) return { yr: r.yr, mn: r.mn };
      return m;
    }, { yr: 0, mn: 0 });
  }

  /** 計算「N個月前」的 yr/mn（民國年） */
  function monthsAgo(yrMn, n) {
    let { yr, mn } = yrMn;
    mn -= n;
    while (mn <= 0) { mn += 12; yr--; }
    return { yr, mn };
  }

  // ═══════════════════════════════════════════════════════════════
  // 🚀  主程式
  // ═══════════════════════════════════════════════════════════════

  // 確認是否在正確的頁面
  if (!window.frames['menuframe'] || !window.frames['targetframe']) {
    UI.fail('❌ 請在登入後的 ebank.banking.gov.tw/Frame 頁面執行此腳本');
    return;
  }

  const lastUpdate = getLastUpdate();
  const isFirstRun = !lastUpdate;

  if (isFirstRun) {
    UI.status(`首次執行，將抓取最近 ${CONFIG.FIRST_RUN_MONTHS} 個月資料...`);
    UI.log(`⚡ 首次執行（localStorage 無記錄）`, '#38bdf8');
    UI.log(`   將抓取最近 ${CONFIG.FIRST_RUN_MONTHS} 個月的資料`, '#64748b');
  } else {
    UI.status(`上次紀錄：民國 ${lastUpdate.yr} 年 ${lastUpdate.mn} 月，搜尋新資料...`);
    UI.log(`📅 上次更新：民國 ${lastUpdate.yr} 年 ${String(lastUpdate.mn).padStart(2,'0')} 月`, '#38bdf8');
    UI.log(`   只會下載此日期之後的新記錄`, '#64748b');
  }

  UI.log('');

  const results       = {};
  let   globalMaxYrMn = { yr: 0, mn: 0 };
  let   totalNew      = 0;

  // ─── 逐一處理每個子項目 ─────────────────────────────────────
  for (let i = 0; i < SUB_ITEMS.length; i++) {
    const item = SUB_ITEMS[i];
    const code = item.name.split('_')[0];

    UI.status(`[${i + 1}/${SUB_ITEMS.length}] 正在處理 ${code}...`);
    UI.progress(i);

    // 1. 導航到該子項目
    const navigated = await navigateTo(item.base);
    if (!navigated) {
      UI.log(`⚠ ${code}：找不到選單連結`, '#f59e0b');
      UI.addErr();
      results[item.name] = { skipped: true, reason: 'menu_link_not_found', details: [] };
      continue;
    }

    // 2. 等待 DataTable 載入
    const ready = await waitForDataTable(CONFIG.PAGE_LOAD_TIMEOUT_SEC);
    if (!ready) {
      UI.log(`⚠ ${code}：DataTable 載入逾時（跳過）`, '#f59e0b');
      UI.addErr();
      results[item.name] = { skipped: true, reason: 'datatable_timeout', details: [] };
      continue;
    }

    // 3. 取得所有列表資料
    const fetched = fetchAllRows();
    if (fetched.error) {
      UI.log(`⚠ ${code}：${fetched.error}（跳過）`, '#f59e0b');
      UI.addErr();
      results[item.name] = { skipped: true, reason: fetched.error, details: [] };
      continue;
    }

    if (fetched.total === 0) {
      UI.log(`  ${code}：無資料`, '#334155');
      UI.addSkip();
      results[item.name] = { totalRows: 0, newRows: 0, details: [] };
      continue;
    }

    // 4. 過濾：只保留新的年月
    let targetRows;
    if (isFirstRun) {
      // 首次：找出系統最新月，往前推 N 個月
      const latest  = maxYrMn(fetched.rows);
      const cutoff  = monthsAgo(latest, CONFIG.FIRST_RUN_MONTHS);
      targetRows = fetched.rows.filter(r =>
        r.yr > cutoff.yr || (r.yr === cutoff.yr && r.mn >= cutoff.mn)
      );
    } else {
      targetRows = fetched.rows.filter(r => isNewer(r, lastUpdate));
    }

    if (targetRows.length === 0) {
      UI.log(`  ${code}：無新資料`, '#334155');
      UI.addSkip();
      results[item.name] = { totalRows: fetched.total, newRows: 0, details: [] };
      continue;
    }

    // 5. 逐筆抓取明細頁面（同步，會短暫鎖住畫面）
    const details = [];
    for (const row of targetRows) {
      let url = `https://ebank.banking.gov.tw${item.base}/Edit?yr=${row.yr}&mn=${row.mn}`;
      if (row.sn !== undefined && row.sn !== null && row.sn !== '') {
        url += `&sn=${row.sn}`;
      }
      try {
        const detail = fetchDetail(url);
        details.push(Object.assign({}, row, detail));
      } catch (e) {
        details.push(Object.assign({}, row, { _fetchError: String(e) }));
      }
    }

    // 6. 更新全局最大年月
    const itemMax = maxYrMn(targetRows);
    if (itemMax.yr > globalMaxYrMn.yr ||
       (itemMax.yr === globalMaxYrMn.yr && itemMax.mn > globalMaxYrMn.mn)) {
      globalMaxYrMn = itemMax;
    }

    totalNew += details.length;
    UI.addNew(details.length);
    UI.log(`✓ ${code}：新增 ${details.length} 筆`, '#34d399');

    results[item.name] = {
      totalRows : fetched.total,
      newRows   : details.length,
      details,
    };
  }

  UI.progress(SUB_ITEMS.length);

  // ─── 下載結果 ────────────────────────────────────────────────
  if (totalNew === 0) {
    UI.done(`✅ 完成！所有項目均無新資料`);
    UI.log('本次無新記錄，未產生下載檔案', '#64748b');
    return;
  }

  // 儲存最新年月到 localStorage
  if (globalMaxYrMn.yr > 0) {
    saveLastUpdate(globalMaxYrMn.yr, globalMaxYrMn.mn);
    UI.log('');
    UI.log(`💾 已記錄最新年月：民國 ${globalMaxYrMn.yr} 年 ${String(globalMaxYrMn.mn).padStart(2,'0')} 月`, '#38bdf8');
  }

  // 產生檔名：ebank_update_115_03.json
  const yrStr = String(globalMaxYrMn.yr);
  const mnStr = String(globalMaxYrMn.mn).padStart(2, '0');
  const filename = `ebank_update_${yrStr}_${mnStr}.json`;

  const payload = {
    scriptVersion : '1.0',
    extractedAt   : new Date().toISOString(),
    latestYrMn    : globalMaxYrMn,
    totalNewRecords: totalNew,
    isFirstRun,
    data: results,
  };

  downloadJSON(filename, payload);

  UI.log(`📥 已觸發下載：${filename}`, '#7dd3fc');
  UI.log(`   共 ${totalNew} 筆新記錄`, '#64748b');
  UI.done(`✅ 完成！新增 ${totalNew} 筆 → ${filename}`);

})();
