(function () {
  'use strict';

  const nativeFetch = window.fetch.bind(window);
  const nativeOpen = window.open.bind(window);
  let dataPromise;

  function loadData() {
    if (!dataPromise) {
      dataPromise = nativeFetch('./data/app-data.json').then(r => {
        if (!r.ok) throw new Error(`無法載入靜態資料 (${r.status})`);
        return r.json();
      });
    }
    return dataPromise;
  }

  function jsonResponse(value, status = 200) {
    return new Response(JSON.stringify(value), {
      status,
      headers: {'Content-Type': 'application/json; charset=utf-8'}
    });
  }

  function number(value) {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(String(value).replace(/,/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function sum(rows, column) {
    const values = rows.map(row => number(row[column])).filter(v => v !== null);
    return values.length ? values.reduce((a, b) => a + b, 0) : null;
  }

  function group(rows, keyFn) {
    const result = new Map();
    rows.forEach(row => {
      const key = keyFn(row);
      if (!result.has(key)) result.set(key, []);
      result.get(key).push(row);
    });
    return result;
  }

  function sortedPeriods(rows, descending = false) {
    const seen = new Map();
    rows.forEach(row => {
      if (row.yr == null || row.mn == null) return;
      seen.set(`${row.yr}/${row.mn}`, {yr: row.yr, mn: row.mn, label: `${row.yr}/${String(row.mn).padStart(2, '0')}`});
    });
    return [...seen.values()].sort((a, b) => {
      const diff = number(a.yr) - number(b.yr) || number(a.mn) - number(b.mn);
      return descending ? -diff : diff;
    });
  }

  function filteredRows(table, params) {
    const yr = number(params.get('yr'));
    const yrTo = number(params.get('yr_to'));
    const mn = number(params.get('mn'));
    const org = params.get('org') || '';
    const scheme = params.get('scheme') || '';
    return table.rows.filter(row =>
      (yr === null || number(row.yr) >= yr) &&
      (yrTo === null || number(row.yr) <= yrTo) &&
      (mn === null || number(row.mn) === mn) &&
      (!org || row['機構名稱'] === org) &&
      (!scheme || row['方案名稱'] === scheme)
    );
  }

  function tableData(table, params) {
    const page = number(params.get('page')) || 1;
    const perPage = number(params.get('per_page')) || 50;
    const structured = params.get('structured') === '1';
    let columns = table.browseColumns;
    let labels = table.browseLabels;
    if (structured && table.structure) {
      columns = [
        ...(table.structure.static || []).map(c => c.col),
        ...(table.structure.groups || []).flatMap(g => g.cols.map(c => c.col))
      ].filter(c => table.columns.includes(c));
      const labelMap = Object.fromEntries(table.browseColumns.map((c, i) => [c, table.browseLabels[i]]));
      labels = columns.map(c => labelMap[c] || c);
    }
    const rows = filteredRows(table, params).sort((a, b) => {
      if (table.columns.includes('yr')) return number(b.yr) - number(a.yr) || number(b.mn) - number(a.mn);
      return table.rows.indexOf(b) - table.rows.indexOf(a);
    });
    const start = (page - 1) * perPage;
    const orgs = [...new Set(table.rows.map(r => r['機構名稱']).filter(v => v != null))].sort();
    const schemes = [...new Set(table.rows.map(r => r['方案名稱']).filter(v => v != null))].sort();
    return {
      columns, col_labels: labels,
      rows: rows.slice(start, start + perPage).map(row => columns.map(c => row[c])),
      total: rows.length, page, per_page: perPage, orgs, schemes
    };
  }

  function compare(table, params) {
    const yr1 = number(params.get('yr1')), mn1 = number(params.get('mn1'));
    const yr2 = number(params.get('yr2')), mn2 = number(params.get('mn2'));
    const org = params.get('org') || '', scheme = params.get('scheme') || '';
    const period = (yr, mn) => table.rows.filter(r =>
      number(r.yr) === yr && number(r.mn) === mn &&
      (!org || r['機構名稱'] === org) && (!scheme || r['方案名稱'] === scheme));
    const left = period(yr1, mn1), right = period(yr2, mn2);
    return {
      label1: `${yr1}/${String(mn1).padStart(2, '0')}`,
      label2: `${yr2}/${String(mn2).padStart(2, '0')}`,
      rows: table.numericColumns.filter(c => !['yr', 'mn'].includes(c.name)).map(c => {
        const v1 = sum(left, c.name), v2 = sum(right, c.name);
        const diff = v1 !== null && v2 !== null ? v2 - v1 : null;
        return {col: c.name, label: c.label, v1, v2, diff, pct: diff !== null && v1 ? Math.round(diff / Math.abs(v1) * 10000) / 100 : null};
      })
    };
  }

  function trend(table, params) {
    const col = params.get('col');
    const org = params.get('org') || '', scheme = params.get('scheme') || '';
    const rows = table.rows.filter(r =>
      r[col] !== null && r[col] !== '' && (!org || r['機構名稱'] === org) && (!scheme || r['方案名稱'] === scheme));
    return [...group(rows, r => `${r.yr}/${r.mn}`).values()].map(items => ({
      yr: items[0].yr, mn: items[0].mn,
      label: `${items[0].yr}/${String(items[0].mn).padStart(2, '0')}`,
      val: sum(items, col)
    })).sort((a, b) => number(a.yr) - number(b.yr) || number(a.mn) - number(b.mn));
  }

  function industry(data, endpoint, params) {
    const rows = (data.tableData['全業者統計'] || {rows: []}).rows;
    if (endpoint === 'periods') return sortedPeriods(rows).map(p => ({yr: p.yr, mn: p.mn, ym: p.label}));
    if (endpoint === 'institutions') return [...new Set(rows.map(r => r['機構名稱']))].sort();
    if (endpoint === 'trend') {
      const metric = params.get('metric') || '使用者人數';
      const inst = params.get('inst') || '';
      const selected = rows.filter(r => !inst || r['機構名稱'] === inst);
      return [...group(selected, r => `${r.yr}/${r.mn}`).values()].map(items => ({
        ym: items[0].ym, yr: items[0].yr, mn: items[0].mn, value: sum(items, metric)
      })).sort((a, b) => number(a.yr) - number(b.yr) || number(a.mn) - number(b.mn));
    }
    if (endpoint === 'latest') {
      const periods = sortedPeriods(rows, true);
      if (!periods.length) return [];
      const p = periods[0];
      return {ym: p.label, data: rows.filter(r => number(r.yr) === number(p.yr) && number(r.mn) === number(p.mn))
        .sort((a, b) => (number(b['各類餘額合計_千元']) || 0) - (number(a['各類餘額合計_千元']) || 0))};
    }
    if (endpoint === 'by_inst') return rows.filter(r => r['機構名稱'] === params.get('inst'));
    return [];
  }

  function monthlyPass(data, endpoint, params) {
    const rows = (data.tableData['月票交易統計'] || {rows: []}).rows;
    if (endpoint === 'periods') return sortedPeriods(rows).map(p => ({yr: p.yr, mn: p.mn, ym: p.label}));
    if (endpoint === 'schemes') {
      const unique = new Map(rows.map(r => [r['方案代碼'], {code: r['方案代碼'], name: r['方案名稱']} ]));
      return [...unique.values()].sort((a, b) => String(a.code).localeCompare(String(b.code)));
    }
    let selected = rows;
    if (endpoint === 'by_scheme' && params.get('ym')) selected = rows.filter(r => r.ym === params.get('ym'));
    if (endpoint === 'trend') selected = rows.filter(r =>
      (!params.get('scheme') || r['方案代碼'] === params.get('scheme')) &&
      (!params.get('sys') || r['體系別'] === params.get('sys')));
    const keyFn = endpoint === 'by_system' ? r => `${r.ym}|${r['體系別']}`
      : endpoint === 'trend' ? r => r.ym
      : r => `${r.ym}|${r['方案代碼']}|${r['方案名稱']}|${r['體系別']}`;
    const result = [...group(selected, keyFn).values()].map(items => ({
      ym: items[0].ym, yr: items[0].yr, mn: items[0].mn,
      '方案代碼': items[0]['方案代碼'], '方案名稱': items[0]['方案名稱'], '體系別': items[0]['體系別'],
      '交易筆數': sum(items, '交易筆數'), '交易金額': sum(items, '交易金額')
    })).sort((a, b) => number(a.yr) - number(b.yr) || number(a.mn) - number(b.mn) || String(a['方案代碼']).localeCompare(String(b['方案代碼'])));
    return result;
  }

  async function route(url) {
    const data = await loadData();
    const parsed = new URL(url, location.href);
    const path = parsed.pathname;
    if (path === '/api/dashboard') return jsonResponse(data.dashboard);
    if (path === '/api/tables') return jsonResponse(data.tables);
    if (path === '/api/docs') return new Response(data.docs, {headers: {'Content-Type': 'text/plain; charset=utf-8'}});
    if (path === '/api/import_log') return jsonResponse([]);
    if (path === '/api/chat/status') return jsonResponse({ollama: false, error: '靜態網站不提供本機 Ollama'});
    if (path === '/api/import' || path === '/api/chat' || path === '/api/chat/clear') {
      return jsonResponse({error: '此功能僅限本機 Flask 版本使用'}, 503);
    }
    const tableMatch = path.match(/^\/api\/table\/([^/]+)\/(months|columns|structure|data|compare|trend)$/);
    if (tableMatch) {
      const table = data.tableData[decodeURIComponent(tableMatch[1])];
      if (!table) return jsonResponse({error: '資料表不存在'}, 404);
      const action = tableMatch[2];
      if (action === 'months') return jsonResponse(sortedPeriods(table.rows, true));
      if (action === 'columns') return jsonResponse(table.numericColumns);
      if (action === 'structure') return jsonResponse(table.structure);
      if (action === 'data') return jsonResponse(tableData(table, parsed.searchParams));
      if (action === 'compare') return jsonResponse(compare(table, parsed.searchParams));
      if (action === 'trend') return jsonResponse(trend(table, parsed.searchParams));
    }
    const industryMatch = path.match(/^\/api\/industry\/(periods|institutions|trend|latest|by_inst)$/);
    if (industryMatch) return jsonResponse(industry(data, industryMatch[1], parsed.searchParams));
    const mpMatch = path.match(/^\/api\/monthly_pass\/(periods|schemes|by_system|by_scheme|trend|scheme_monthly)$/);
    if (mpMatch) return jsonResponse(monthlyPass(data, mpMatch[1], parsed.searchParams));
    return jsonResponse({error: `靜態 API 尚未支援：${path}`}, 404);
  }

  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : input.url;
    const parsed = new URL(url, location.href);
    if (parsed.pathname.startsWith('/api/')) return route(url, init);
    return nativeFetch(input, init);
  };

  window.open = function (url, target, features) {
    const parsed = new URL(url, location.href);
    const match = parsed.pathname.match(/^\/api\/table\/([^/]+)\/export$/);
    if (!match) return nativeOpen(url, target, features);
    loadData().then(data => {
      const code = decodeURIComponent(match[1]);
      const table = data.tableData[code];
      const columns = table.columns.filter(c => !data.skipColumns.includes(c));
      const rows = filteredRows(table, parsed.searchParams);
      const escape = value => `"${String(value == null ? '' : value).replace(/"/g, '""')}"`;
      const csv = '\ufeff' + [columns, ...rows.map(r => columns.map(c => r[c]))].map(row => row.map(escape).join(',')).join('\r\n');
      const blobUrl = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = `${code}_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}.csv`;
      link.click();
      URL.revokeObjectURL(blobUrl);
    });
    return null;
  };

  window.FSC_STATIC_MODE = true;

  document.addEventListener('DOMContentLoaded', () => {
    ['import', 'chat'].forEach(page => {
      const link = document.querySelector(`#sidebar .nav-link[data-page="${page}"]`);
      if (link) {
        link.title = '此功能僅限本機 Flask 版本';
        link.insertAdjacentHTML('beforeend', '<span style="margin-left:auto;font-size:9px;color:#fbbf24">本機限定</span>');
      }
      const panel = document.getElementById(`page-${page}`);
      if (panel) {
        const notice = document.createElement('div');
        notice.className = 'alert alert-warning py-2 px-3 mb-3';
        notice.innerHTML = '<i class="bi bi-info-circle me-1"></i>此功能需要本機 Flask／SQLite 服務，靜態網站僅提供資料查詢與分析。';
        panel.insertBefore(notice, panel.children[1] || null);
      }
    });
  });
})();
